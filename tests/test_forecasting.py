import numpy as np, pandas as pd
from ml.features.demand import build_demand_features,make_supervised
from ml.training.baselines import naive_forecast,moving_average_forecast
from ml.evaluation.metrics import evaluate

def test_features_and_metrics():
    dates=pd.date_range("2024-01-01",periods=40)
    df=pd.DataFrame({"date":dates,"product_id":"p1","demand":np.arange(1,41)})
    f=build_demand_features(df)
    s=make_supervised(f)
    assert len(s)>20
    assert set(["lag_1","lag_7","rolling_mean_7","dow","month"]).issubset(s.columns)
    pred=naive_forecast([1,2,3],5)
    assert len(pred)==5
    scores=evaluate([1,2,3],[1,3,2])
    assert set(scores)=={"MAE","RMSE","WAPE","sMAPE"}

def test_selected_baseline_is_persisted_and_inference_supports_required_horizons(tmp_path):
    import pandas as pd
    from ml.training.train_forecast import ForecastTrainer
    from ml.inference.forecast import ForecastInference
    dates=pd.date_range('2020-01-01', periods=40)
    df=pd.DataFrame({'date':dates,'product_id':['p1']*40,'demand':[1]*40})
    features=build_demand_features(df)
    trainer=ForecastTrainer(tmp_path)
    _,winner=trainer.train(features)
    assert (tmp_path/'demand_forecast.joblib').exists()
    inf=ForecastInference(tmp_path/'demand_forecast.joblib')
    assert len(inf.predict(features,7))==7
    assert len(inf.predict(features,30))==30
    assert len(inf.predict(features,90))==90
