import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

def mae(y_true,y_pred): return float(mean_absolute_error(y_true,y_pred))
def rmse(y_true,y_pred): return float(np.sqrt(mean_squared_error(y_true,y_pred)))
def wape(y_true,y_pred):
    denom=float(np.sum(np.abs(y_true)))
    return float(np.sum(np.abs(np.asarray(y_true)-np.asarray(y_pred)))/denom) if denom else 0.0
def smape(y_true,y_pred):
    a=np.asarray(y_true,dtype=float); b=np.asarray(y_pred,dtype=float)
    denom=np.abs(a)+np.abs(b)
    return float(np.mean(np.where(denom==0,0,2*np.abs(a-b)/denom)))
def evaluate(y_true,y_pred):
    return {"MAE":mae(y_true,y_pred),"RMSE":rmse(y_true,y_pred),"WAPE":wape(y_true,y_pred),"sMAPE":smape(y_true,y_pred)}
