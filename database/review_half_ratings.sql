alter table public.reviews
  drop constraint if exists reviews_rating_check;

alter table public.reviews
  alter column rating type numeric(2, 1)
  using rating::numeric(2, 1);

alter table public.reviews
  add constraint reviews_rating_check
  check (
    rating between 0.5 and 5
    and rating * 2 = trunc(rating * 2)
  );
