from pathlib import Path
import sys, json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configs.settings import settings
from ml.stockout.model import build_stockout_dataset, StockoutModel
from ml.stockout.shap_explain import explain
from ml.suppliers.intelligence import build_supplier_intelligence
from ml.warehouses.intelligence import warehouse_metrics,recommend_allocation,transfer_recommendations
from ml.delivery.model import build_delivery_dataset,DeliveryRiskModel
from ml.optimization.model import SupplyOptimizer

def main():
    st=settings.staging_data_dir; pr=settings.processed_data_dir; models=settings.model_dir; pr.mkdir(parents=True,exist_ok=True); models.mkdir(parents=True,exist_ok=True)
    inv=pd.read_csv(pr/'inventory_snapshots.csv'); wh=pd.read_csv(pr/'warehouses.csv'); sup=pd.read_csv(pr/'suppliers.csv'); sp=pd.read_csv(pr/'supplier_products.csv'); po=pd.read_csv(pr/'purchase_orders.csv'); demand=pd.read_csv(pr/'daily_product_demand.csv')
    # Phase 6
    sd=build_stockout_dataset(inv,demand,sup,sp); sd.to_csv(pr/'stockout_features.csv',index=False); sm=StockoutModel(models); smetrics=sm.train(sd); pred=sm.predict(sd); pred.to_csv(pr/'stockout_predictions.csv',index=False); shap=explain(sm.load()['model'],sd[sm.load()['features']].sample(min(2000,len(sd)),random_state=42)); shap.to_csv(pr/'stockout_shap_global.csv',index=False)
    # Phase 7
    si=build_supplier_intelligence(sup,po); si.to_csv(pr/'supplier_intelligence.csv',index=False)
    # Phase 8
    wm=warehouse_metrics(wh,inv); wm.to_csv(pr/'warehouse_metrics.csv',index=False); alloc=recommend_allocation(wh,inv,sd); alloc.to_csv(pr/'recommended_inventory_by_warehouse.csv',index=False); tr=transfer_recommendations(wh,inv,sd); tr.to_csv(pr/'warehouse_transfer_recommendations.csv',index=False)
    # Phase 9
    orders=pd.read_csv(st/'orders.csv'); items=pd.read_csv(st/'order_items.csv'); products=pd.read_csv(st/'products.csv'); sellers=pd.read_csv(st/'sellers.csv'); customers=pd.read_csv(st/'customers.csv'); geo=pd.read_csv(st/'geolocation.csv')
    dd=build_delivery_dataset(orders,items,products,sellers,customers,geo); dd.to_csv(pr/'delivery_risk_features.csv',index=False); dm=DeliveryRiskModel(models); dscores,dwinner=dm.train(dd); dp=dm.predict(dd); dp.to_csv(pr/'delivery_risk_predictions.csv',index=False)
    # Phase 10
    opt=SupplyOptimizer().solve(sup,wh,sd,inv); opt.supplier_quantities.to_csv(pr/'optimization_supplier_quantities.csv',index=False); opt.warehouse_quantities.to_csv(pr/'optimization_warehouse_quantities.csv',index=False); opt.transfers.to_csv(pr/'optimization_transfers.csv',index=False)
    summary={'phase6':{'metrics':smetrics},'phase7':{'suppliers':len(si)},'phase8':{'warehouses':len(wm),'allocation_rows':len(alloc),'transfer_rows':len(tr)},'phase9':{'selected_model':dwinner,'metrics':dscores},'phase10':{'solver':opt.solver,'current_cost':opt.current_cost,'optimized_cost':opt.optimized_cost,'estimated_savings':opt.current_cost-opt.optimized_cost,'service_level':opt.service_level,'stockout_risk':opt.stockout_risk}}
    (pr/'phase6_10_summary.json').write_text(json.dumps(summary,indent=2,default=str))
    print(json.dumps(summary,indent=2,default=str))
if __name__=='__main__': main()
