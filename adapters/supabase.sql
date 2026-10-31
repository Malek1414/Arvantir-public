-- Arvantir -> Supabase (Postgres 15+)
--
-- Idee aus "Designing Data-Intensive Applications" (Kleppmann), Kap. 11/12:
--   raw_pages      = System of Record. Nur INSERT, nie UPDATE/DELETE (Trigger unten).
--   companies, people, field_values, lead_scores = abgeleitete Daten.
--   Die darf man jederzeit leeren und aus raw_pages neu berechnen
--   (neuer Normalisierer, neues Re-Ranker-Modell -> einfach neu ableiten).
--
-- Jeder Feldwert trägt Provenienz: source_url, raw_page_id, method, confidence, ts.
-- Entity-Schlüssel (eine Firma = eine Zeile):
--   reg:<gericht>|<HRB>  >  dom:<registrierbare domain>  >  name:<gefalteter name>|<PLZ>
-- Erzeugt in adapters/clay.py:entity_key, damit Clay und Supabase denselben Schlüssel haben.
--
-- Einspielen: Supabase Dashboard -> SQL Editor -> diese Datei ausführen.
-- RLS ist überall an und ohne Policies: nur der Service-Role-Key (Server) kommt dran,
-- nie der anon-Key aus einem Frontend.

-- ---------------------------------------------------------------- Läufe
create table if not exists runs (
  id           text primary key,                 -- z. B. run_130450
  seed         text not null,                    -- Nische oder Beispiel-URL
  niche        text,
  icp          text,                             -- Re-Ranker-Query
  model        text,                             -- RERANKER_MODEL des Laufs
  funnel       jsonb not null default '[]',      -- [{step, n, t}]
  seconds      numeric,
  created_at   timestamptz not null default now()
);

-- ------------------------------------------------- System of Record (unveränderlich)
create table if not exists raw_pages (
  id            bigint generated always as identity primary key,
  url           text not null,
  kind          text not null check (kind in ('list', 'list_entry', 'profile', 'impressum',
                                              'team', 'jobs', 'api', 'other')),
  body          text not null,                   -- HTML oder extrahierter Text, wie geholt
  content_sha256 text not null default '',      -- setzt der Trigger beim INSERT
  http_status   int,
  run_id        text references runs(id),
  fetched_at    timestamptz not null default now(),
  unique (url, content_sha256)                   -- gleiche Seite, gleicher Inhalt = ein Eintrag
);
create index if not exists raw_pages_url on raw_pages (url);

create or replace function raw_pages_immutable() returns trigger language plpgsql as $$
begin
  raise exception 'raw_pages ist das System of Record: nur INSERT erlaubt';
end $$;

create or replace function raw_pages_hash() returns trigger language plpgsql as $$
begin
  new.content_sha256 := encode(sha256(convert_to(new.body, 'UTF8')), 'hex');
  return new;
end $$;

drop trigger if exists raw_pages_hash on raw_pages;
create trigger raw_pages_hash before insert on raw_pages
  for each row execute function raw_pages_hash();

drop trigger if exists raw_pages_no_update on raw_pages;
create trigger raw_pages_no_update before update or delete on raw_pages
  for each row execute function raw_pages_immutable();

-- ---------------------------------------------------------------- abgeleitet: Firmen
create table if not exists companies (
  entity_key     text primary key,
  key_kind       text not null check (key_kind in ('register', 'domain', 'name_plz')),
  name           text not null,
  legal_form     text,
  domain         text,
  postcode       text,
  city           text,
  country        text,
  register_court text,
  register_number text,
  in_ai_ark      boolean,                        -- null = nicht geprüft; nur false zählt als dark
  source_count   int not null default 1,         -- auf wie vielen Listen: Legitimitäts-Signal
  first_seen     timestamptz not null default now(),
  last_seen      timestamptz not null default now()
);
create index if not exists companies_domain on companies (domain);
create unique index if not exists companies_register
  on companies (register_court, register_number) where register_number is not null;

-- Alte Schlüssel zeigen auf neue (Firma bekommt später HRB -> Schlüssel wird stärker).
create table if not exists entity_aliases (
  old_key   text primary key,
  new_key   text not null references companies(entity_key) on delete cascade,
  merged_at timestamptz not null default now()
);

-- Woher kennen wir die Firma? (eine Zeile pro Liste)
create table if not exists company_sources (
  entity_key  text not null references companies(entity_key) on delete cascade,
  source_url  text not null,
  source_type text,                              -- Verband, Messe, Kammer, Partnerverzeichnis ...
  run_id      text references runs(id),
  raw_page_id bigint references raw_pages(id),
  seen_at     timestamptz not null default now(),
  primary key (entity_key, source_url)
);

-- ---------------------------------------------------------------- abgeleitet: Personen
create table if not exists people (
  id          uuid primary key default gen_random_uuid(),
  entity_key  text not null references companies(entity_key) on delete cascade,
  full_name   text not null,
  role        text,
  linkedin    text,
  created_at  timestamptz not null default now(),
  unique (entity_key, full_name)
);

-- ---------------------------------------------------- abgeleitet: Feldwerte mit Provenienz
-- Jede Beobachtung bleibt stehen. Mehrere Werte pro Feld sind erlaubt;
-- die View company_fields_current wählt den besten.
create table if not exists field_values (
  id          bigint generated always as identity primary key,
  entity_key  text not null references companies(entity_key) on delete cascade,
  person_id   uuid references people(id) on delete cascade,  -- null = Firmenfeld
  field       text not null,                     -- email, phone, fax, vat_id, employees, locations ...
  value       text not null,
  source_url  text,                              -- wo es steht
  raw_page_id bigint references raw_pages(id),   -- welcher Abzug genau
  method      text not null,                     -- regex, llm, api:aiark, api:blitz, api:lusha, inferred
  confidence  numeric(3,2) not null check (confidence between 0 and 1),
  evidence    text,                              -- Zitat aus der Quelle
  ts          timestamptz not null default now(),
  unique nulls not distinct (entity_key, person_id, field, value, source_url)
);
create index if not exists field_values_lookup on field_values (entity_key, field);

-- ------------------------------------------------- abgeleitet: Bewertung pro Lauf
create table if not exists lead_scores (
  run_id        text not null references runs(id) on delete cascade,
  entity_key    text not null references companies(entity_key) on delete cascade,
  score         int not null check (score between 0 and 100),   -- Re-Ranker 0-100
  tier          text generated always as (
                  case when score >= 80 then 'A' when score >= 60 then 'B'
                       when score >= 40 then 'C' else 'D' end) stored,  -- wie icp-scorer
  confidence    text,                            -- hoch / mittel / niedrig
  needs_human   boolean not null default false,  -- nah an der Schwelle -> SDR entscheidet
  reason        text,                            -- bester Profilsatz
  reason_source text,
  channel       text,
  draft         text,
  scored_at     timestamptz not null default now(),
  primary key (run_id, entity_key)
);

-- ---------------------------------------------------------------- Views für SDRs
create or replace view company_fields_current as
select distinct on (entity_key, person_id, field)
       entity_key, person_id, field, value, source_url, method, confidence, ts
from field_values
order by entity_key, person_id, field, confidence desc, ts desc;

-- Eine Zeile pro Lead, letzter Lauf zuerst. Spalten wie adapters/clay.py.
create or replace view sdr_leads as
select c.entity_key, c.name, c.domain, c.city, c.postcode, c.in_ai_ark,
       c.in_ai_ark is false as dark_tam, c.source_count,
       s.score, s.tier, s.confidence, s.needs_human, s.reason, s.reason_source, s.channel,
       p.full_name as decision_maker, p.role as decision_maker_role,
       (select value from company_fields_current f
         where f.entity_key = c.entity_key and f.person_id = p.id and f.field = 'email') as work_email,
       (select value from company_fields_current f
         where f.entity_key = c.entity_key and f.person_id is null and f.field = 'phone') as phone,
       s.run_id, s.scored_at
from companies c
join lateral (select * from lead_scores ls where ls.entity_key = c.entity_key
              order by scored_at desc limit 1) s on true
left join lateral (select * from people pp where pp.entity_key = c.entity_key
                   order by created_at limit 1) p on true;

-- Firmen einspielen ohne bekannte Werte zu verlieren: ein späterer Lauf ohne
-- AI-Ark-Check oder HRB überschreibt vorhandene Werte nicht mit null.
create or replace function upsert_companies(rows jsonb) returns int language sql as $$
  with ins as (
    insert into companies as c (entity_key, key_kind, name, legal_form, domain, postcode, city,
                                country, register_court, register_number, in_ai_ark, source_count, last_seen)
    select r.entity_key, r.key_kind, r.name, r.legal_form, r.domain, r.postcode, r.city, r.country,
           r.register_court, r.register_number, r.in_ai_ark, coalesce(r.source_count, 1),
           coalesce(r.last_seen, now())
    from jsonb_populate_recordset(null::companies, rows) r
    on conflict (entity_key) do update set
      name            = excluded.name,
      key_kind        = excluded.key_kind,
      legal_form      = coalesce(excluded.legal_form, c.legal_form),
      domain          = coalesce(excluded.domain, c.domain),
      postcode        = coalesce(excluded.postcode, c.postcode),
      city            = coalesce(excluded.city, c.city),
      country         = coalesce(excluded.country, c.country),
      register_court  = coalesce(excluded.register_court, c.register_court),
      register_number = coalesce(excluded.register_number, c.register_number),
      in_ai_ark       = coalesce(excluded.in_ai_ark, c.in_ai_ark),
      source_count    = greatest(excluded.source_count, c.source_count),
      last_seen       = excluded.last_seen
    returning 1)
  select count(*)::int from ins;
$$;

-- Neu ableiten: abgeleitete Tabellen leeren, raw_pages bleibt.
-- Danach den Normalisierer / adapters/supabase.py erneut laufen lassen.
create or replace function rebuild_derived() returns void language sql as $$
  truncate lead_scores, field_values, people, company_sources, entity_aliases, companies;
$$;

-- ---------------------------------------------------------------- Zugriff
alter table runs            enable row level security;
alter table raw_pages       enable row level security;
alter table companies       enable row level security;
alter table entity_aliases  enable row level security;
alter table company_sources enable row level security;
alter table people          enable row level security;
alter table field_values    enable row level security;
alter table lead_scores     enable row level security;
alter view company_fields_current set (security_invoker = on);
alter view sdr_leads set (security_invoker = on);
revoke execute on function rebuild_derived() from public, anon, authenticated;
revoke execute on function upsert_companies(jsonb) from public, anon, authenticated;
