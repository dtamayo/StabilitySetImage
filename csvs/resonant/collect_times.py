import pandas as pd
import numpy as np
import os
import rebound
import sys
import gc

def get_times(row):
    print(fcpath+row["runstring"])
    try:
        
        sim = rebound.SimulationArchive(fcpath + row["runstring"])
        columns = ['t']
        features = sim[-1].t
        print ('{0:.16f}'.format(sim[-1].t))

        del sim 
    except Exception as e:
        print(e)
        columns= ['t']
        features = [ np.nan ]
    return pd.Series(features, index=columns)



path = "../data"
files = ['Res_sys_{0}_1e8'.format(sys.argv[1])]


for file_name in files:
    fcpath = path + "resonant_distributions/{0}/simulation_archives/sa".format(file_name)
    df= pd.read_csv(path+"/resonant_distributions/{0}/{1}.csv".format(file_name, file_name.split("_")[2].split("_")[0] ))
    df = pd.concat([df, df.apply(get_times, axis = 1)], axis = 1)
    df.to_csv("resonant_features/{0}{1}.csv".format(file_name.split("1e")[0],df.shape[0] ), index = False)
    del df