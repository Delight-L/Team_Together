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

// Selection always uses pages counted from the first fixed tab, so a temporary
// narrow/loading layout cannot leave the first fixed tab hidden after resizing.
export function tabPageForSelected(widths, selectedIndex, availableWidth) {
  const selected = Math.max(0, Math.min(selectedIndex, widths.length - 1));
  let page = tabPage(widths, 0, availableWidth);
  while (page.end <= selected && page.end < widths.length) {
    page = tabPage(widths, page.end, availableWidth);
  }
  return page;
}
