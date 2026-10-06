// Shared decorative relief; the original administrative boundaries are preserved.
function districtTile(unit, color, attribute, label) {
  const selected = unit.n === S.sel;
  return `<g class="district-tile ${selected ? 'is-selected' : ''}" ${attribute} tabindex="0" role="button" aria-label="${esc(label)}"><title>${esc(label)}</title><path class="district-hit" d="${unit.d}"/><path class="district-base" d="${unit.d}" transform="translate(0 7)"/><g class="district-top"><path class="mission-district" d="${unit.d}" fill="${color}"/><text class="actual-map-label" x="${unit.cx}" y="${unit.cy}" text-anchor="middle">${esc(unit.n)}</text></g></g>`;
}
function reliefMap(geometry, tiles, label) {
  return `<svg viewBox="-35 -35 ${geometry.w + 70} ${geometry.h + 70}" role="group" aria-label="${esc(label)}"><g transform="skewX(-4) scale(1 .94)">${tiles}</g></svg>`;
}
listen('keydown', event => {
  const tile = event.target.closest?.('[data-overview-district]');
  if (tile && S.user && ['Enter', ' '].includes(event.key)) {
    event.preventDefault();
    openRegionAnalysis(tile.dataset.overviewDistrict);
  }
});

listen('pointerover',event=>{
  const tile=event.target.closest?.('.district-tile');
  if(tile && tile.parentElement.lastElementChild!==tile) tile.parentElement.appendChild(tile);
});
