from __future__ import annotations
from pathlib import Path
import joblib, pandas as pd
from common.config import CONFIG, Analysis1Config
from analysis.analysis1 import build_feature_table, balance_domains, fit_final_clusters
PCA_COLUMNS={'active_pop':['male_ratio','age_10_ratio','age_20_ratio','age_30_ratio','age_40_ratio','age_50_ratio','age_60_plus_ratio'],'time_structure':['night_ratio','morning_ratio','daytime_ratio','evening_ratio'],'resident_age':['resident_ratio_0_19','resident_ratio_20_29','resident_ratio_30_39','resident_ratio_40_49','resident_ratio_50_64','resident_ratio_65_plus'],'household_structure':['hh_1_ratio','hh_2_ratio','hh_3_ratio','hh_4plus_ratio']}
CLUSTER_TYPE={0:'고활동·청년유동·1인가구 중심형',1:'고령·2인가구·구조적 복지배경 특화형',2:'중간활동·다인가구 중심형'}
def fit_baseline(base_df,config=CONFIG):
 f,a=build_feature_table(base_df,pca_columns=PCA_COLUMNS,config=config); b,s=balance_domains(f,config); c,k=fit_final_clusters(f,b,config); c['cluster_type']=c.cluster.map(CLUSTER_TYPE)
 bundle={'baseline_period':'2025H2','pca_columns':PCA_COLUMNS,'pca':a['pca'],'feature_scaler':s,'kmeans':k,'domains':config.domains,'cluster_type':CLUSTER_TYPE,'baseline_features':f.copy(),'baseline_balanced':b.copy(),'baseline_clusters':c[[config.area_key,config.area_name,'cluster','cluster_type']].copy()}
 return f,b,c,bundle
def save_baseline(base_df,output_dir,config=CONFIG,results_dir=None):
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
 results=Path(results_dir) if results_dir is not None else out
 results.mkdir(parents=True,exist_ok=True); f,b,c,bundle=fit_baseline(base_df,config)
 f.to_csv(results/'gangnam_analysis1_features_2025H2.csv',index=False,encoding='utf-8-sig'); pd.concat([f[[config.area_key,config.area_name]].reset_index(drop=True),b.reset_index(drop=True)],axis=1).to_csv(results/'gangnam_analysis1_balanced_features_2025H2.csv',index=False,encoding='utf-8-sig'); c.to_csv(results/'gangnam_analysis1_baseline_clusters_2025H2.csv',index=False,encoding='utf-8-sig'); joblib.dump(bundle,out/'analysis1_baseline_2025H2.joblib'); return f,b,c,bundle
