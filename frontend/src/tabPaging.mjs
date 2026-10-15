// Only complete tabs belong to a page. Previous pages are packed backwards.
export function tabPage(widths, requestedStart, availableWidth) {
  if (!widths.length) return { start: 0, end: 0, previous: 0 };
  const start = Math.max(0, Math.min(requestedStart, widths.length - 1));
  let end = start, used = 0;
  while (end < widths.length) {
    if (end > start && used + widths[end] > availableWidth) break;
    used += widths[end++];
  }
  let previous = start, previousWidth = 0;
  while (previous > 0) {
    const width = widths[previous - 1];
    if (previous < start && previousWidth + width > availableWidth) break;
    previousWidth += width;
    previous--;
  }
  return { start, end, previous };
}

// If the selected tab fits on the first page, show the first page so the fixed tabs
// come back after resizing. Otherwise end the page at the selected tab and include
// as many earlier tabs as fit, so the selected tab never sits alone at a page start.
export function tabPageForSelected(widths, selectedIndex, availableWidth) {
  const selected = Math.max(0, Math.min(selectedIndex, widths.length - 1));
  const first = tabPage(widths, 0, availableWidth);
  if (selected < first.end) return first;
  let start = selected, used = widths[selected] || 0;
  while (start > 0 && used + widths[start - 1] <= availableWidth) used += widths[--start];
  return tabPage(widths, start, availableWidth);
}
