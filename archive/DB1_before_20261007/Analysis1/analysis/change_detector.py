from pathlib import Path
import math,joblib,numpy as np,pandas as pd
from common.config import CONFIG
def _features(df,bundle,config=CONFIG):
 df=df.rename(columns=config.input_feature_map).copy(); keys=[config.area_key,config.area_name]; out=df[keys+['activity_intensity','weekend_weekday_index','foreigner_ratio','disability_ratio','livelihood_recipient_ratio']].copy()
 for p,cols in bundle['pca_columns'].items():
  m=bundle['pca'][p]; sc=m['pca'].transform(m['scaler'].transform(df[cols].astype(float)))[:,:2]; out[p+'_pc1']=sc[:,0]; out[p+'_pc2']=sc[:,1]
 fc=[c for cs in config.domains.values() for c in cs]; return out[keys+fc]
def detect_changes(base_df,bundle_or_path,period,config=CONFIG):
 from data.validation import validate_table,require_pass
 base_df=base_df.copy().reset_index(drop=True)
 base_df[config.area_key]=base_df[config.area_key].astype(str)
 loaded=joblib.load(bundle_or_path) if isinstance(bundle_or_path,(str,Path)) else bundle_or_path
 required=list(dict.fromkeys(['flow_per_point','weekend_weekday_index','foreigner_ratio','disability_ratio','livelihood_recipient_ratio']+[c for cs in loaded['pca_columns'].values() for c in cs]))
 require_pass(validate_table(base_df,[config.area_key,config.area_name]+required,area_key=config.area_key,expected_areas=22,unique_area=True,non_numeric_columns=[config.area_key,config.area_name]))
 if set(base_df[config.area_key])!=set(loaded['baseline_features'][config.area_key].astype(str)):
  raise ValueError('Current area codes must match baseline')
 bundle_or_path=loaded
 bundle=joblib.load(bundle_or_path) if isinstance(bundle_or_path,(str,Path)) else bundle_or_path; cur=_features(base_df,bundle,config); fc=[c for cs in config.domains.values() for c in cs]
 bal=pd.DataFrame(bundle['feature_scaler'].transform(cur[fc]),columns=fc,index=cur.index)
 for cs in config.domains.values(): bal.loc[:,list(cs)]*=1/math.sqrt(len(cs))
 model=bundle['kmeans']; labels=model.predict(bal); dist=model.transform(bal); res=cur[[config.area_key,config.area_name]].copy(); res.insert(2,'period',period); res['current_cluster']=labels; res['current_cluster_type']=res.current_cluster.map(bundle['cluster_type']); res['current_centroid_distance']=dist[np.arange(len(labels)),labels]
 bc=bundle['baseline_clusters'].rename(columns={'cluster':'baseline_cluster','cluster_type':'baseline_cluster_type'}).copy(); bc[config.area_key]=bc[config.area_key].astype(str); res=res.merge(bc.drop(columns=[config.area_name]),on=[config.area_key],validate='one_to_one'); res['cluster_changed']=res.current_cluster!=res.baseline_cluster
 bf=bundle['baseline_features'].copy(); bf[config.area_key]=bf[config.area_key].astype(str); dm=cur.merge(bf.drop(columns=[config.area_name]),on=[config.area_key],suffixes=('_current','_baseline'),validate='one_to_one');
 for c in fc: res=res.merge(dm[[config.area_key,config.area_name]].assign(**{f'delta_{c}':dm[f'{c}_current']-dm[f'{c}_baseline']}),on=[config.area_key,config.area_name],validate='one_to_one')
 bb=bundle['baseline_balanced'].copy(); bb.index=bf[config.area_key].astype(str).values
 for domain,cs in config.domains.items():
  vals=[]
  for i,row in cur.iterrows(): vals.append(float(np.linalg.norm(bal.iloc[i][list(cs)].to_numpy()-bb.loc[str(row[config.area_key]),list(cs)].to_numpy())))
  res[f'{domain}_distance_from_baseline']=vals
 baseline_codes=bundle['baseline_clusters'].copy(); baseline_codes[config.area_key]=baseline_codes[config.area_key].astype(str)
 old_labels=baseline_codes.set_index(config.area_key).loc[cur[config.area_key],'cluster'].to_numpy(int)
 aligned=bb.loc[cur[config.area_key]].to_numpy(float)
 old_distance=np.linalg.norm(aligned-model.cluster_centers_[old_labels],axis=1)
 res['centroid_distance_delta']=res.current_centroid_distance.to_numpy()-old_distance
 return cur,bal,res
