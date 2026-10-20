export function reviewGroups(reviews = []) {
  const groups = new Map();
  reviews.forEach((review, index) => {
    const key = review.service_key || `record:${index}`;
    const previous = groups.get(key);
    groups.set(key, { key, latest: review, history: previous ? [...previous.history, previous.latest] : [] });
  });
  return [...groups.values()];
}
