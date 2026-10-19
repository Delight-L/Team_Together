import {detectionTabs} from './ageSignals.mjs';

export function serviceCaseOptions(analysis, context) {
  return context.city === '강남구' ? detectionTabs(analysis?.ageDetections || [],context.city,context.month) : [];
}

export function resolveServiceCase(analysis, context) {
  const items=serviceCaseOptions(analysis,context);
  const selected=items.find(item => item.district===context.district && item.age===context.age) || items[0];
  return selected ? {city:context.city,month:context.month,district:selected.district,age:selected.age}
    : {city:context.city,month:context.month,district:'',age:''};
}

export function dashboardCaseFocus(analysis, context, requestId) {
  const detection=serviceDetection(analysis,context);
  return {...context,code:detection?.code,sex:'통합',requestId};
}

// Carry the detection month, never the follow-up observation end month.
export function selectedServiceContext(view, context, group, tracking) {
  const selected = view === 'dashboard' ? group : view === 'map' ? tracking : context;
  if (!selected) return { city:context.city, district:'', month:context.month };
  return { city:selected.city, district:selected.district || '', month:selected.month,
    ...(selected.age ? {age:selected.age} : {}) };
}

export function serviceDetection(analysis, context) {
  if (context.city !== '강남구' || !context.district || !context.age || !context.month) return null;
  return (analysis?.ageDetections || []).find(c =>
    c.district === context.district && c.age === context.age && c.month === context.month) || null;
}

export function serviceDomains(detection) {
  return [['communication','통신',['call_contacts','text_contacts']],
    ['mobility','이동',['weekday_move_count','weekend_move_count']]]
    .filter(([key]) => detection?.[key+'_signal'] === true)
    .map(([key,label,metrics]) => {
      const absolute = detection.payload?.[key+'_absolute_signal'] === true;
      const local = detection.payload?.[key+'_local_signal'] === true;
      return {key,label,metrics,absolute,local,
        state:absolute && local ? 'both' : absolute ? 'absolute' : local ? 'local' : 'none'};
    });
}

// A deliberate click stores the evidence first, then confirms review.
// A failed registration must never be followed by a confirmation request.
export async function confirmServiceEvidence(workflow, mutate) {
  let current = workflow;
  if (!current.done?.includes(0)) {
    current = await mutate('/workflow/start');
    if (!current) return null;
  }
  return current.done?.includes(1) ? current : mutate('/workflow/confirm');
}
