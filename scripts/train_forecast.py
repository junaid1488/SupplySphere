from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.settings import settings
from ml.features.demand import build_demand_features
from ml.training.train_forecast import ForecastTrainer
import pandas as pd

if __name__ == "__main__":
    path=settings.processed_data_dir/"daily_product_demand.csv"
    if not path.exists():
        # Build daily demand from staged Olist files.
        orders=pd.read_csv(settings.staging_data_dir/"orders.csv")
        items=pd.read_csv(settings.staging_data_dir/"order_items.csv")
        orders["date"]=pd.to_datetime(orders["order_purchase_timestamp"],errors="coerce").dt.floor("D")
        d=items.merge(orders[["order_id","date"]],on="order_id",how="left")
        daily=d.groupby(["date","product_id"],as_index=False).agg(demand=("order_item_id","count"))
        path.parent.mkdir(parents=True,exist_ok=True)
        daily.to_csv(path,index=False)
    daily=pd.read_csv(path)
    features=build_demand_features(daily)
    scores,winner=ForecastTrainer(settings.model_dir).train(features)
    print("Selected:",winner)
    print(scores)
