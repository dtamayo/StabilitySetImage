import numpy as np
import emcee
import pandas as pd
import rebound
import os
from scipy.stats import norm, ks_2samp
import dask.dataframe as dd

if rebound.__githash__ != '6fb912f615ca542b670ab591375191d1ed914672':
    print('Check out rebound commit 6fb912f615ca542b670ab591375191d1ed914672 and rerun script')
    exit()

seed = 0
np.random.seed(seed)
nwalkers = 20
ndim = 2
iterations = 1000

def lnprob(p, vec):
    diff = vec-p[0]
    N = len(vec)

    if p[1] <=0:
        return -np.inf
    try:
        probs = -0.5 * N * np.log(2. * np.pi) - N/2. * np.log(np.abs(p[1])**2) - 0.5 \
                                    * np.sum(( (vec - p[0]) / p[1] ) ** 2)
    except:
        probs = 0.00
    return probs
       
def log_prob_normed(mu, sigma, info):
    prob = -np.log(2*np.pi)/2. - np.log(sigma**2.)/2.-(1./(sigma**2.)/2./info.shape[0])*np.nansum((info-mu)**2.)
    return prob

def collision(reb_sim, col):
    reb_sim.contents._status = 5
    return 0

def es(system, Nshadows, tmax=1.e4):
    distpath = 'hussain2019data/resonant_distributions/'
    folder = distpath + "Res_sys_{0}_1e8/simulation_archives/".format(system)#ic{1:0=7d}.bin".format(system, 0)
    root, dirs, files = next(os.walk(folder))
    Nsys=0
    for file in files:
        try:
            sim = rebound.SimulationArchive(folder+file)[0]
            Nsys += 1
        except:
            print('Didnt load')
    Nout = 1000
    data = np.zeros((Nsys+1, Nout))
    for j, file in enumerate(files[:Nshadows]):
        sim = rebound.SimulationArchive(folder+file)[0]
        sim.collision_resolve = collision
        sim.exit_max_distance = 100.
        ps = sim.particles
        times = np.logspace(0, np.log10(tmax), Nout)
        for i, time in enumerate(times):
            try:
                sim.integrate(time)
                data[j, i] = ps[2].e
            except:
                break
    data[-1,:] = times
    return data

def run(row):
    tmax = 1e7
    ID = int(row['ID'])
    
    systemdir = distpath+'Res_sys_{0}_1e8/'.format(ID)
    for file in os.listdir(systemdir):
        if 'csv' in file:
            data = pd.read_csv(systemdir+file, index_col=0)
            data = data.apply(get_times, args=(systemdir,), axis=1)
            data.to_csv(csvpath+'Res_sys_{0}_{1}.csv'.format(ID, data.shape[0]))
            
    realization = data.loc[0]
    row['instability_time'] = realization['t']
    file = distpath+"Res_sys_{0}_1e8/simulation_archives/sa".format(ID)+realization['runstring']
    
    data = data[data["t"]<1e8]
    data = np.log10(data["t"].values)
    
    p0 = [np.random.rand(ndim) for i in range(nwalkers)]
    sampler = emcee.EnsembleSampler(nwalkers, ndim, lnprob, args=[data], a=5)
    
    # Run 200 steps as a burn-in.
    pos, prob, state = sampler.run_mcmc(p0, 200)
    sampler.reset()
    pos, prob, state = sampler.run_mcmc(pos, iterations, rstate0=seed)
    
    maxprob_indice = np.argmax(prob)
    mean_fit, sigma_fit = pos[maxprob_indice]
    sigma_fit = np.abs(sigma_fit) 
    row['Mean'] = mean_fit
    row['Sigma'] = sigma_fit
    
    test = np.random.normal(loc=row['Mean'], scale=row['Sigma'], size = data.shape[0])

    try:
        statistic, KSpval = ks_2samp(data, test)
    except:
        statistic, KSpval = 0,0
        
    row['KSpval'] = KSpval
    
    sim = rebound.SimulationArchive(file)[0]
    sim.ri_whfast.keep_unsynchronized = 1
    sim.collision_resolve=collision
    sim.init_megno(seed=0)

    Nout = 1000
    times = np.logspace(0, np.log10(tmax), Nout)
    P0 = sim.particles[1].P

    try:
        sim.integrate(row['instability_time']/10, exact_finish_time=0)
        row['tlyap10'] = 1/sim.calculate_lyapunov()/P0
        if row['tlyap10'] < 0 or row['tlyap10'] > sim.t:
            row['tlyap10'] = sim.t
        row['Nlyap10'] = row['instability_time']  / row['tlyap10']
    except:
        row['tlyap10'] = np.nan
        row['Nlyap10'] = np.nan
    
    return row

def get_times(row, args):
    systemdir = args
    fcpath = systemdir+"/simulation_archives/sa"
    try:
        sa = rebound.SimulationArchive(fcpath + row["runstring"])
        row['t'] = sa[-1].t
        del sa
    except Exception as e:
        row['t'] = np.nan
    return row

# trappist instability times

trappistdistpath = 'hussain2019data/trappist/simulation_archives/'
for root, dirs, files in os.walk(trappistdistpath):
    binaries = files
    break

def final_time(filename):
    try:
        sa = rebound.SimulationArchive(trappistdistpath + filename)
        sim = sa[0]
        P0 = sim.particles[1].P
        return sa[-1].t/P0
    except Exception as e:
        print(e, filename)
        return np.nan

trappisttimes = [final_time(f) for f in binaries]

trap = pd.DataFrame(np.array([binaries, trappisttimes]).T, columns=['runstring', 't'])
trap.to_csv('csvs/trappist.csv')

# generate shadow eccentricity time histories for the two sample peaked and lognormal distributions

Nshadows = 50
peakedID = 60
lognormID = 14

datapeaked = es(peakedID, Nshadows=Nshadows, tmax=2.e4)
datalognorm = es(lognormID, Nshadows=Nshadows, tmax=1.e5)

np.savetxt('csvs/peakedID_60_shadows.npy', datapeaked)
np.savetxt('csvs/lognormID_14_shadows.npy', datalognorm)

# resonanat systems

csvpath = "csvs/resonant_distributions/"
distpath = 'hussain2019data/resonant_distributions/'
for root, dirs, files in os.walk(distpath):
    planet_systems = dirs
    break

df = pd.DataFrame([s.split("_")[-2] for s in planet_systems], columns=["ID"])
df = df.sort_values("ID")
df = df.reset_index(drop=True)

ddf = dd.from_pandas(df, npartitions=24)
testres = run(df.iloc[0])
df = ddf.apply(run, axis=1, meta=pd.DataFrame([testres])).compute(scheduler='processes')

df.to_csv('csvs/resonant_summary.csv')
