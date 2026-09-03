alter table public.reviews
  drop constraint if exists reviews_rating_check;

alter table public.reviews
  add constraint reviews_rating_check
  check (
    rating between 0.5 and 5
    and rating * 2 = trunc(rating * 2)
  );
