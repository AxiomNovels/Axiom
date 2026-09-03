drop policy if exists "Users can delete their own reviews" on public.reviews;

create policy "Users can delete their own reviews"
  on public.reviews for delete
  using (auth.uid() = user_id);
