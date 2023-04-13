from py_vollib.black_scholes import black_scholes
from py_vollib.black_scholes.greeks.analytical import delta
from py_vollib.black_scholes.greeks.analytical import gamma
from py_vollib.black_scholes.greeks.analytical import theta
from py_vollib.black_scholes.greeks.analytical import vega
from py_vollib.black_scholes.greeks.analytical import rho
from py_vollib.black_scholes.greeks.numerical import delta as ndelta
from py_vollib.black_scholes.greeks.numerical import gamma as ngamma
from py_vollib.black_scholes.greeks.numerical import theta as ntheta
from py_vollib.black_scholes.greeks.numerical import vega as nvega
from py_vollib.black_scholes.greeks.numerical import rho as nrho
import json
import math
import csv


RUN_DURATION = 0.25 - (0.25/3.0)
PERIOD_DURATION = RUN_DURATION/600



def pricer(flag, S, K, t, r, sigma): # Takes all the arguments and applied black_scholes model to price option
    return black_scholes(flag, S, K, t, r, sigma)

def read_target(fileName, period_column, flag, K): #Reads Market premium of the option on the csv file and writes it in params.json
    if flag == "c":
        option_column = f"call{K}"
    elif flag == "p":
        option_column = f"put{K}"
    with open(fileName, 'r') as file:
        reader = csv.reader(file)
        header = next(reader)
        option_index = header.index(option_column)
        for i, row in enumerate(reader):
            if i == period_column:
                return float(row[option_index])

S_array = [65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135]

def timeToMaturity(numberOfPeriods): #Evaluates time to maturity
    return 0.25 - numberOfPeriods*PERIOD_DURATION



def calibrate(flag, S, K, periods, r, sigma, target):
    ttm = timeToMaturity(periods)
    price = pricer(flag, S, K, ttm, r, sigma)
    while not math.isclose(price, target, rel_tol=0.01):
        if price < target:
            sigma += 0.001
        elif price > target:
            sigma -= 0.001
        price = pricer(flag, S, K, ttm, r, sigma)
    print(f"Theoretical Price: {price}, Actual Price: {target}, Implied Volatility: {sigma}")
    return sigma 

implied_volatility = calibrate('c', 100, 100, 0, 0, 0.2, read_target("/Users/macbookpro/Desktop/xchange-v1.0.2-115-g6b94+8ef0/data/case2/training_pricepaths.csv", 0, "c", 100))
print(implied_volatility)

prices = []
for K in S_array:
    prices.append(pricer('c', 100, K, timeToMaturity(0), 0, implied_volatility)) 
    

print(prices)

def greeks (flag, S, K, t, r, sigma):
    delta1 = delta(flag, S, K, t, r, sigma)
    gamma1 = gamma(flag, S, K, t, r, sigma)
    theta1 = theta(flag, S, K, t, r, sigma)
    vega1 = vega(flag, S, K, t, r, sigma)
    rho1 = rho(flag, S, K, t, r, sigma)

        # Open the existing .json file
    with open('/Users/macbookpro/Desktop/xchange-v1.0.2-115-g6b94+8ef0/clients/params.json', 'r') as f:
        data = json.load(f)

    # Add the variables to the dictionary
    data['delta'] = delta1
    data['gamma'] = gamma1
    data['theta'] = theta1
    data['vega'] = vega1
    data['rho'] = rho1

    # Write the updated dictionary back to the .json file
    with open('/Users/macbookpro/Desktop/xchange-v1.0.2-115-g6b94+8ef0/clients/params.json', 'w') as f:
        json.dump(data, f)

greeks('c', 100, K, timeToMaturity(0), 0, implied_volatility)




