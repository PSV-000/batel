import pprint
from datetime import datetime
from copy import deepcopy

# Constants
cashConstant = "$CASH" # Identifies cash in trade transactions
nonPriceKeys = ["Quantity", "SKU", cashConstant]

# Table of Contents (Methods)
    # totalUnitBasis
    # totalProductBasis
    # totalQuantity
    # averageCost
    # profitOrLoss
    # transactionSort
    # processTrade

def totalUnitBasis(costDictionary):
    basis = 0
    for key in sorted(costDictionary.keys()):
        if key in nonPriceKeys:
            continue
        else:
            basis += costDictionary[key]
    return basis

def totalProductBasis(costDictionary):
    basis = 0
    for key in sorted(costDictionary.keys()):
        if key in nonPriceKeys:
            continue
        else:
            basis += costDictionary[key]
    return basis * costDictionary["Quantity"]

def aggregatePriceDates(costDictionary):
    # Extracts {Date : Price} dictionary items and scale to quantity
    aggregates = {}
    #tempQuantity = 0
    for key in sorted(costDictionary.keys()):
        if key in nonPriceKeys:
            continue
        else:
            try:
                aggregates[key] += costDictionary[key]
            except KeyError:
                aggregates[key] = costDictionary[key]
        try:
            aggregates[key] = aggregates[key] * costDictionary["Quantity"] #tempQuantity
        except KeyError:
            pass
    return aggregates

def joinPrice(firstDictionary, secondDictionary):
    # Binds {Date : Price} dictionary items together
    first = aggregatePriceDates(firstDictionary)
    second = aggregatePriceDates(secondDictionary)
    for key in sorted(second.keys()):
        try:
            first[key] += second[key]
        except KeyError:
            first[key] = second[key]
    return first

def arrayPriceDates(salesArray):
    # Behaves as aggregatePriceDates for array of cost dictionaries
    total = {}
    for sale in salesArray:
        total = joinPrice(total, sale)
    return total

def totalQuantity(pricingArray):
    quantityCount = 0
    for unit in pricingArray:
        quantityCount += unit["Quantity"]
    return quantityCount

def averageCost(pricingArray):
    allCosts = []
    for unit in pricingArray:
        indCost = totalUnitBasis(unit)
        allCosts.append(indCost * unit["Quantity"])
    totalCost = 0
    for eachCost in allCosts:
        totalCost += eachCost
    if totalQuantity(pricingArray) == 0:
        return None
    else:
        return totalCost/totalQuantity(pricingArray)

def profitOrLoss(saleDictionary):
    # Move to venture economics
    MOIC = averageCost(saleDictionary["Sale"]) + averageCost(saleDictionary["Cost"]) # Adding because costs are negative
    try:
        return saleDictionary["Sale"][0]["Quantity"] * MOIC # Items are sold at one price, can use average unit price
    except TypeError:
        return 0

def transactionSort(transactions):
    # Sequence as (1) Buy, (2) Trade, (3) Sell
    # Consider building trade sequencing logic (e.g. push failed trades to the end of trade queue)
    for dated, transact in transactions.items():
        newList = []
        buyTrack = 0
        tradeTrack = 0
        for trans in transact:
            if trans["Type"] == "BUY":
                newList.insert(0, trans)
                buyTrack += 1
            elif trans["Type"] == "TRADE":
                newList.insert(buyTrack + tradeTrack, trans)
                tradeTrack += 1
            elif trans["Type"] == "SELL":
                newList.append(trans)
        transactions[dated] = newList

def processTrade(tradeDictionary, inventory, orderBoolean, sales):
    realPrices = []
    costIndex = 0
    tempSalesDictionary = {}
    for tradesOut in tradeDictionary["Out"]:
        # Cards traded away need to be moved out of inventory and potentially into sales
        newAppends = [] # Copy of incremental appends to realPrices, for potential inclusion to sales
        newIndex = 0
        # Isolated cash: outgoing cash will blend in with total cost, without need for additional differentiation
        if tradesOut["SKU"] == cashConstant:
            tempCashOut = {
                tradesOut["Date"]: tradesOut["Price"],
                "Quantity": 1
                }
            realPrices.append(deepcopy(tempCashOut))
            newAppends.append(deepcopy(tempCashOut))
            costIndex += 1
        else:
            # Look in inventory for item
            removeCount = 0
            while removeCount < tradesOut["Quantity"]:
                for inv in inventory[int(tradesOut["SKU"])]:
                    if orderBoolean:
                        orderBoolean = False # Filler action - should search inventory for items to move to sales
                    else:
                        # Move items from inventory to temporary trade array
                        inventoryClone = deepcopy(inv) # Require deep copy to not overwrite inventory quantity
                        realPrices.append(inventoryClone)
                        newAppends.append(inventoryClone)
                        incrementalRemoved = min(inventoryClone["Quantity"], tradesOut["Quantity"] - removeCount)
                        realPrices[costIndex]["Quantity"] = incrementalRemoved
                        newAppends[newIndex]["Quantity"] = incrementalRemoved
                        costIndex += 1
                        newIndex += 1

                        # Remove traded items from inventory
                        removeCount += incrementalRemoved
                        if incrementalRemoved >= inv["Quantity"]:
                            inventory[int(tradesOut["SKU"])].pop(0)
                            if inventory[int(tradesOut["SKU"])] == []:
                                inventory.pop(int(tradesOut["SKU"]), None) # Maintain "Active Inventory"
                        else:
                            inv["Quantity"] -= incrementalRemoved # Reduce inventory quantity
            tempSalesDictionary[tradesOut["SKU"]] = newAppends

    # Calculate the pass-through cost of incoming trades (i.e. the "real" cost of the trade)
    realTotalBasis = {}
    for priceCombo in realPrices:
        for priceDates in sorted(priceCombo.keys()):
            if priceDates in nonPriceKeys:
                continue
            else:
                try:
                    realTotalBasis[priceDates] += (priceCombo[priceDates] * priceCombo["Quantity"])
                except:
                    realTotalBasis[priceDates] = (priceCombo[priceDates] * priceCombo["Quantity"])

    # Nominal basis required to calculate pro-rata share of incoming trade basis
    nominalBasis = 0
    cashInflow = 0
    cashDate = "" # Dates are formatted as strings
    for tradesIn in tradeDictionary["In"]:
        if tradesIn["SKU"] == cashConstant:
            cashInflow += tradesIn["Price"]
            cashDate = tradesIn["Date"]
        else:
            nominalBasis += tradesIn["Price"] * tradesIn["Quantity"]

    # If cash inflow is greater than pass-through cost/true basis, the trade is a disguised sale
    if cashInflow >= abs(totalUnitBasis(realTotalBasis)):
        # Add trades to inventory as $0 cost basis
        for tradesIn in tradeDictionary["In"]:
            if tradesIn["SKU"] == cashConstant:
                continue
            else:
                tempTradesIn = {
                    cashDate: 0,
                    "Quantity": tradesIn["Quantity"]
                    }
                try:
                    inventory[int(tradesIn["SKU"])].append(tempTradesIn)
                except:
                    inventory[int(tradesIn["SKU"])] = [tempTradesIn]
        # Move all outgoing inventory to sales
        totalResolvedBasis = 0
        for resolvedBasis in tempSalesDictionary.keys():
            avgCost = averageCost(tempSalesDictionary[resolvedBasis])
            totalCards = totalQuantity(tempSalesDictionary[resolvedBasis])
            totalResolvedBasis += avgCost * totalCards
        # Distribute the sales proceeds by each card's pro-rata share in the cost
        for resolvedBasis in tempSalesDictionary.keys():
            avgCost = averageCost(tempSalesDictionary[resolvedBasis])
            totalCards = totalQuantity(tempSalesDictionary[resolvedBasis])
            tempSaleDetail = {
                cashDate: (avgCost * totalCards)/totalResolvedBasis * cashInflow,
                "Quantity": totalCards
                }
            tempSaleShell = {
                "Cost": tempSalesDictionary[resolvedBasis],
                "Sale": [tempSaleDetail],
                "SKU": resolvedBasis
                }
            sales.append(tempSaleShell)
    else:
        # Adjust total basis by cash inflow amount
        if cashInflow != 0:
            try:
                realTotalBasis[cashDate] += cashInflow
            except:
                realTotalBasis[cashDate] = cashInflow

        # Add incoming trades to inventory
        for tradesIn in tradeDictionary["In"]:
            if tradesIn["SKU"] == cashConstant:
                continue
            else:
                tempInput = {"Quantity": tradesIn["Quantity"]}
                for priceDates in realTotalBasis.keys():
                    basisClone = deepcopy(realTotalBasis[priceDates])
                    try:
                        tempInput[priceDates] += (tradesIn["Price"] / nominalBasis * basisClone)
                    except:
                        tempInput[priceDates] = (tradesIn["Price"] / nominalBasis * basisClone)
                try:
                    inventory[int(tradesIn["SKU"])].append(tempInput)
                except:
                    inventory[int(tradesIn["SKU"])] = [tempInput]
