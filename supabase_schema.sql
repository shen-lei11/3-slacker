-- Run this once in Supabase SQL Editor.

create table if not exists users (
  id bigserial primary key,
  name text not null,
  email text unique not null,
  password_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists tasks (
  id bigserial primary key,
  title text not null,
  description text,
  status text not null default 'todo',
  priority text not null default 'medium',
  deadline date,
  user_id bigint not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint tasks_user_fk foreign key (user_id) references users(id) on delete cascade
);

create table if not exists current_focus (
  id bigserial primary key,
  user_id bigint not null,
  title text not null,
  description text,
  status_note text,
  target_date date,
  updated_at timestamptz not null default now(),
  constraint current_focus_user_fk foreign key (user_id) references users(id) on delete cascade
);

create table if not exists backlog_items (
  id bigserial primary key,
  title text not null,
  description text,
  category text not null default 'shared',
  created_by bigint not null,
  created_at timestamptz not null default now(),
  constraint backlog_items_creator_fk foreign key (created_by) references users(id) on delete cascade
);

create table if not exists achievements (
  id bigserial primary key,
  title text not null,
  description text,
  user_id bigint not null,
  date_achieved date not null default current_date,
  created_at timestamptz not null default now(),
  constraint achievements_user_fk foreign key (user_id) references users(id) on delete cascade
);

create table if not exists slacking_jar_entries (
  id bigserial primary key,
  user_id bigint not null,
  reason text not null,
  amount float not null default 1.0,
  is_paid boolean not null default false,
  issued_by bigint not null,
  date_issued timestamptz not null default now(),
  constraint sje_target_fk foreign key (user_id) references users(id) on delete cascade,
  constraint sje_issuer_fk foreign key (issued_by) references users(id)
);

create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists tasks_updated_at on tasks;
create trigger tasks_updated_at before update on tasks
  for each row execute function set_updated_at();

drop trigger if exists current_focus_updated_at on current_focus;
create trigger current_focus_updated_at before update on current_focus
  for each row execute function set_updated_at();

alter table users disable row level security;
alter table tasks disable row level security;
alter table current_focus disable row level security;
alter table backlog_items disable row level security;
alter table achievements disable row level security;
alter table slacking_jar_entries disable row level security;
