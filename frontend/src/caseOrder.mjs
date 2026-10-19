const names = new Intl.Collator('ko', {numeric:true, sensitivity:'base'});
const district = value => value.district || value.name || value.n || '';
const ageNumber = value => Number.parseInt(String(value.age || value.age_label || value.age_band || ''),10);
// One order for directories and selectors: name, natural dong number, then age.
export function compareDistrictAge(a,b) {
  const nameOrder=names.compare(district(a),district(b));
  if(nameOrder) return nameOrder;
  const x=ageNumber(a),y=ageNumber(b);
  return (Number.isFinite(x)?x:Infinity)-(Number.isFinite(y)?y:Infinity) || names.compare(a.age || a.age_band || '',b.age || b.age_band || '');
}
export const orderedCases = items => [...items].sort(compareDistrictAge);
