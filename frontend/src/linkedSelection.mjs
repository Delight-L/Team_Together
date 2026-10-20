import {orderedCases} from './caseOrder.mjs';
import {detectionTabs} from './ageSignals.mjs';
import {groupKey} from './groupTabs.mjs';

// Visible observations may include a deliberately selected non-detection group.
// Detection counts and detection selectors continue to use detectionTabs only.
export function overviewWorkspace(cases,city,month,selection,previous) {
  const observations=orderedCases(cases.filter(row=>row.month===month));
  const tabs=detectionTabs(cases,city,month);
  const requested=selection?.district&&selection?.age;
  const row=observations.find(row=>requested ? row.district===selection.district&&row.age===selection.age
    : row.code===previous?.code&&row.age===previous?.age) || (!requested ? observations.find(row=>row.any_signal)||observations[0] : null);
  const selected=row ? {city,code:row.code,district:row.district,age:row.age,sex:'통합',month} : null;
  if(selected&&!tabs.some(group=>groupKey(group)===groupKey(selected)))tabs.push(selected);
  return {tabs,active:selected?groupKey(selected):''};
}

export function trackingCase(tracking,context,signalMonth) {
  const events=(tracking?.events||[]).filter(event=>event.signalMonth<=context.month);
  const months=[...new Set(events.map(event=>event.signalMonth))].sort();
  const matching=(tracking?.events||[]).filter(event=>event.district===context.district&&event.age===context.age&&event.signalMonth<=context.month)
    .sort((a,b)=>a.signalMonth.localeCompare(b.signalMonth));
  const month=matching.find(event=>event.signalMonth===signalMonth)?.signalMonth||matching.at(-1)?.signalMonth||
    (months.includes(signalMonth)?signalMonth:months.at(-1)||context.month);
  return {month,event:matching.find(event=>event.signalMonth===month)||null};
}

export function signalForGroup(tracking,context,preferred) {
  const matching=(tracking?.events||[]).filter(event=>event.district===context.district&&event.age===context.age&&event.signalMonth<=context.month)
    .sort((a,b)=>a.signalMonth.localeCompare(b.signalMonth));
  return matching.find(event=>event.signalMonth===preferred)?.signalMonth||matching.at(-1)?.signalMonth||preferred;
}
