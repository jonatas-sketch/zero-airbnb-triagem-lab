create role airbnb_course_reader nologin;
grant airbnb_course_reader to authenticator;

create table public.airbnb_course_bookings (
  imported_row integer primary key,
  booking_id text not null,
  checkin_at text not null,
  checkout_at text not null,
  refund_status text,
  refund_amount numeric(12,2),
  refund_currency text,
  wifi_available boolean not null,
  wifi_help_reference text not null,
  checkin_instructions_status text not null,
  listing_city text not null
);
create index airbnb_course_booking_id_idx on public.airbnb_course_bookings(booking_id);
alter table public.airbnb_course_bookings enable row level security;
revoke all privileges on table public.airbnb_course_bookings from anon, authenticated, public;
grant usage on schema public to airbnb_course_reader;
grant select (booking_id, checkin_at, checkout_at, refund_status, refund_amount,
              refund_currency, wifi_available, wifi_help_reference,
              checkin_instructions_status, listing_city)
on public.airbnb_course_bookings to airbnb_course_reader;
create policy course_reader_select on public.airbnb_course_bookings
  for select to airbnb_course_reader using (true);
