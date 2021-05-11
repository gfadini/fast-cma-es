
import time, sys, warnings

from fcmaes import retry, advretry
from fcmaes.optimizer import logger, de_cma, Bite_cpp, De_cpp, Cma_cpp, LDe_cpp, Minimize, dtime
from fcmaes.de import DE
from fcmaes.cmaes import Cmaes
import numpy as np
from scipy.integrate import ode
from scipy.optimize import Bounds

import ctypes as ct
import multiprocessing as mp 
import pylab as p
from numba.tests.test_array_constants import dt

# Definition of parameters from https://scipy-cookbook.readthedocs.io/items/LoktaVolterraTutorial.html
a = 1.
b = 0.1
c = 1.5
d = b*0.75
pop0 = [10, 5] # initial population 10 rabbits, 5 foxes at t0 = 0
dim = 20 # years
bounds = Bounds([-1]*dim, [1]*dim) # X[i] < 0 means: no fox killing this year

# RawValue works with parallel fitness calls (at least on unix)
bval = mp.RawValue(ct.c_double, 1E99) # best value so far
evals = mp.RawValue(ct.c_int, 0) # number of evaluations
time0 = time.perf_counter() # optimization start time

# Lodka Volterra differential equations 
# Propagates a population of x rabbits and y foxes
def lotkavolterra(t, pop, a, b, c, d):
    x, y = pop
    return [a*x - b*x*y, -c*y + d*x*y]

def integrator():
    I = ode(lotkavolterra)
    # see https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.ode.html
    # the “dopri5” integrator is reentrant
    I.set_integrator("dopri5", nsteps=1000, rtol=1e-6, atol=1e-6)
    I.set_f_params(a,b,c,d)
    return I

def integrate(I, t):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return I.integrate(t)

# maximal rabbit population after dim years of fox killings 
def fitness(X):
    t0 = 0 # start time 
    t1 = len(X) # end time, check after dim = len(X) years
    pop = pop0 # initial population 
    ts = []
    for year, x in enumerate(X):
        if x > 0: # should we kill a fox this year? 
            ts.append(t0 + year + x) # when exactly?
    ts.append(t1) # append end time
    I = integrator()
    I.set_initial_value(pop, t0)
    for i in range(len(ts)):
        #propagate rabbit and fox population to ts[i]      
        pop = integrate(I, ts[i]) 
        if i < len(ts)-1:           
            # kill one fox, but keep at least one
            pop[1] = max(1, pop[1]-1) 
            I.set_initial_value(pop, ts[i])
    # value is maximal rabbit population during the following 5 years without fox killings

    max_rabbits = 0
    for t in np.linspace(t1, t1 + 5, 50): # check every 0.1 years for 5 years
        pop = integrate(I, t)
        max_rabbits = max(max_rabbits, pop[0])
    value = -max_rabbits  
    # book keeping and logging
    evals.value += 1
    if value < bval.value and value < 1E99:
        bval.value = value
        logger().info("nfev = {0}: t = {1:.1f} fval = {2:.3f} fox kill at {3:s} x = {4:s}"
            .format(evals.value, dtime(time0), value, str([round(t,2) for t in ts[:-1]]), str(list(X))))
    return value     

# parallel optimization with smart boundary management, DE works best
def smart_retry(opt = De_cpp(1500)):
    return advretry.minimize(fitness, bounds, optimizer=opt, num_retries=50000, max_eval_fac=20)

# parallel independent optimization, BiteOpt works best
def parallel_retry(opt = Bite_cpp(100000, M=8)):
    return retry.minimize(fitness, bounds, optimizer=opt)

# parallel independent optimization for improvement of an existing solution. Bite_cpp, LDe_cpp and Cma_cpp can be used.
def parallel_improve(opt):
    return retry.minimize(fitness, bounds, optimizer=opt)

# parallel function evaluation, single optimization, DE works best
def parallel_eval(opt = DE(dim, bounds)):
    return opt.do_optimize_delayed_update(fun=fitness, max_evals=5000000)

solution = [0.776493606911633, 5.313367199186114e-11, -0.01911689944376108, 0.999999999998243, 0.9999999999999777, 0.8778065780316634, -0.9677096355465782, 0.9877828448885166, 0.21691071881497626, -0.1944392073928476, 1.0, 0.7622846184132999, -2.0391328917626546e-06, -0.22780030500674903, -0.6537913248006114, 0.8517517878859682, 1.774349183498689e-16, 1.0, 1.0, 0.1509101207001727]

if __name__ == '__main__':
    bval.value = -1E99 
    print("shoot no fox at all, fitness =", fitness([-0.5]*dim)) 
    print("shoot a fox every year, fitness =", fitness([0.5]*dim)) 
    print("best solution, fitness =", fitness(solution))
    bval.value = 1E99
    
    # lets find the best solution
    ret = smart_retry()    
    #ret = parallel_retry()
    #ret = parallel_eval()
    #parallel_improve(Bite_cpp(1000000, M=16, guess=sol))
    #parallel_improve(LDe_cpp(1000000, guess=sol))
    #parallel_improve(Cma_cpp(1000000, guess=sol))

    #parallel_retry(opt = Minimize(500000))
