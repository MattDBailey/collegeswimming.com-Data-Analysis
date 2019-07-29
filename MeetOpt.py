"""
Author: Brad Beacham
email: blb032@bucknell.edu

Adapted from code by Matt Bailey
email: mdb025@bucknell.edu

Created on Wed July 24 2019
"""
#NEED: 
    #MaxSolveTime minutes of solve time
    #OptGap decimal gap to stop 0-1 search

#Import PuLP modeller functions
from math import *
import pulp
import time
import os
from constants import *
import pandas as pd
from gurobipy import *

def generate_ghost_players(pred_perf):
    """
    :param pred_perf: predicted performance matrix of a single team.
    :return ghosts: dataframe of RELAY_TEAM_SIZE number of ghosts. This many ghosts are needed due to hard relay
    requirements
    """
    vals = []
    cols = []
    ghost_list = []
    # get times and columns for ghost dataframe
    for col in pred_perf:
        vals.append(max(pred_perf[col].dropna()))
        cols.append(col)
    # assign index values for ghosts
    for i in range(RELAY_TEAM_SIZE):
        ghost_list.append("ghost{}".format(i))

    ghosts = pd.DataFrame([vals] * RELAY_TEAM_SIZE, columns=cols, index=ghost_list)
    return ghosts


def format_pred_perf(pred_perf):
    """
    This function takes in a predicted performance pandas dataframe for one team and finds all of the worst non-NA times
    scored by that team. It then fills all of the NA values in the predicted performance table with the default time
    for their column. Finally, the pandas dataframe is converted into a dictionary
    # NOTE: ultimately, it would probably be best if we can avoid converting this to a dictionary and just keep using
        # pandas the whole time, but due to time constraints I can't find a way to do that right now.
    :param pred_perf: predicted performance matrix of a team.
    :return formatted_perf: the pred_perf dictionary of a team, described above
    """
    # a dictionary of "default times" made of the worst times scored in each event.
    default_times = {}
    for event in pred_perf:
        default_times[event] = max(pred_perf[event].dropna())
    # fill all of the NA values in the pred perf with default times, then convert it to a dictionary and return it
    formatted_perf = pred_perf.fillna(value=default_times, inplace=False)
    print(formatted_perf)
    formatted_perf = formatted_perf.to_dict(orient="index")
    return formatted_perf



def meet_opt(pred_perf_list, home_lineups, opponent_lineups, probability_matrix):
    """

    :param pred_perf_list: list of predicted performance matrices/dataframes. The first dataframe is for the home team
    :param home_lineups: list of lineups used by home team
    :param opponent_lineups: list of lineups used by opponent team
    :param probability_matrix: list of probabilities of each opponent lineup being used
    :return:
    """
    ## Begin INPUT SETTINGS
    # 1 if want to write output to file at the following path
    # WriteOutput = 0
    # path of the output file adjust for user
    # would not  append to a file created in the SolverStudio working files folder
    # if WriteOutput == 1:
    #    path = "G:\My Drive\SwimMeetOpt" + "\SwimMeetOptTrialResults.csv"

    # Set solve time limit in seconds and optimality gap
    # MaxSolveTime = 100
    solver_time_limit = MAX_SOLVE_TIME * 60

    # Which Solver?
    if SOLVER_USED == "CBC":
        # Choose solver, and set it to problem, and build the model
        # Solve with CBC with logging and time limit. Parameter option: keepFiles=1 breaks it!
        # solver = pulp.COIN_CMD(msg=1, keepFiles=1, presolve=0, threads=1, maxSeconds=solver_time_limit,fracGap = OPT_GAP)
        solver = pulp.COIN_CMD(msg=1, keepFiles=1, presolve=1, maxSeconds=solver_time_limit, fracGap=OPT_GAP)
    else:
        # Solve with Gurobi
        # Wouldn't work without changing SolverStudio settings to reference "GUROBI_CL.exe" (command line)
        # solver = pulp.GUROBI_CMD(keepFiles=1,options=[("MIPFocus",1),("TimeLimit",solver_time_limit)])
        solver = pulp.GUROBI_CMD(keepFiles=1,
                                 options=[("MIPFocus", 1), ("MIPGap", OPT_GAP), ("TimeLimit", solver_time_limit)])

        # Solve with Cplex. Throws error for write sol file
        # solver = pulp.CPLEX_scCMD(msg=1,options = ['set mip tolerances mipgap 0.2'])
        # solver = pulp.CPLEX_CMD(msg=1,timelimit=30)

    ## End INPUT SETTINGS

    # DATA arrays from Excel workbook:
    # %data: athlete set, event set, stroke set,  event_noMR set, event11 set, indivrun set, relay set, relaynoMR set, homerank set, opprank set, place set, scenario set, probability_matrix[scenario], BigM[event11], opptime[opprank,event11,scenario], playperf[athlete, event_noMR], playperfMR[athlete, stroke],indivplcscore[place], relayplcscore[place], Maxevent, Maxindevent, Maxrelayevent, TopopprankIndiv, TopopprankRelay

    # small constant
    EPS = 0.0001;

    # Just solve the whole problem (NO VORP calculation)
    # athletetest = ""

    # realathlete are only the actual athletes
    realathlete = pred_perf_list[0].index.tolist()

    # subset of the actual athletes with some ghosts because of hard relay requirements
    home_with_ghosts = pd.concat(pred_perf_list[0], generate_ghost_players())
    # list of athletes including "ghost" athletes
    athlete = home_with_ghosts.index.tolist()

    # for i in realathlete:
    #    print("current realathlete index ", realathlete.index(i))
    #    print("previous athlete ", realathlete[realathlete.index(i)-1])

    # OUTPUT Arrays and Variables

    # Objective Value
    # OptObj

    # Scenario scores vs. opps
    # scenscore[scenario]: real[0..]
    # if assigned athlete has 1st time in event
    # x[athlete,event_noMR]: binary
    # if assigned athlete has 2nd best time in event
    # y[athlete,event_noMR]: binary
    # if assigned athlete has 3rd best time in event
    # z[athlete, event_noMR]: binary
    # if assigned athlete has 1st time in medley
    # xMR[athlete,stroke]: binary
    # if assigned athlete has 2nd best time in medley
    # yMR[athlete,stroke]: binary
    # if assigned athlete has 3rd best time in medley
    # zMR[athlete, stroke]: binary
    # rank of our athletes assigned to events
    # r[homerank,event11]: real
    # indicator variables of for outcome of event j versus opp 1
    # w[event11,homerank, place, scenario]: binary

    # assignments
    # asgn[athlete,event]: binary;

    # Start the clock for first setup
    setup_start = time.time()

    print("Check Done")

    # Instantiate our problem class
    SwimMeetOpt = pulp.LpProblem("MeetMax", pulp.LpMaximize)

    # Initialize the decision variables
    # Scenario scores vs. opps
    scenscorevars = {}
    # if assigned athlete has 1st time in event
    xvars = {}
    # if assigned athlete has 2nd best time in event
    yvars = {}
    # if assigned athlete has 3rd best time in event
    zvars = {}
    # if assigned athlete has 1st time in start time in event 200MR
    xvarstarts = {}
    # if assigned athlete has 2nd best time in start time in event 200MR
    yvarstarts = {}
    # if assigned athlete has 3rd best time in start time in event 200MR
    zvarstarts = {}
    # if assigned athlete has 1st time in medley
    xMRvars = {}
    # if assigned athlete has 2nd best time in medley
    yMRvars = {}
    # if assigned athlete has 3rd best time in medley
    zMRvars = {}
    # rank of our athletes assigned to events
    rvars = {}
    # indicator variables of for outcome of event j versus opp 1
    wvars = {}
    # assignments
    asgnvars = {}

    # OPTIMIZATION DECISION VARIABLES defined in the MeetOpt paper using PuLP:

    # scenscorevar is a placeholder which will hold the expected score of our optimal
    # lineup against the lineup given in scenario i
    scenario = range(len(opponent_lineups))
    scenscorevar = LpVariable.dicts('scenscorevar', (scenario), 0, None, LpContinuous)

    # these are placement variables for our athletes to events
    # xvar will hold the best assigned athlete from our team in an event
    # yvar will hold the second best assigned athlete from our team in an event
    # zvar will hold the third best assigned athlete from our team in an event
    # We assume that exactly three athletes are assigned to each event
    # the optimization creates the assignment and the ordering

    # NOTE: confirm all of these lists on a windows computer

    # here we build up all of our event name lists
    indiv = []  # the list of all individual events
    event_noMR = []  # the list of all events, excluding medley relay strokes
    relaynoMR = []  # the list of all relays, excluding medley relay strokes
    stroke = []  # the list of all medley relay strokes/legs
    event11 = []  # the list of all events contested, excluding medley relay strokes
    event = []  # list of individual events, relay events, and medley relay strokes
    relay = []  # list of relay names
    for event_name in pred_perf_list[0]:
        # build indiv, which is the list of all individual events
        event.append(event_name)
        if event_name[2] not in "MF":  # check to see if event is an individual event
            indiv.append(event_name)
            event_noMR.append(event_name)
            event11.append(event_name)
        if event_name[2] in "MF":  # check to see if event is a relay event
            if event_name[2] in "F":  # it is a freestyle relay stroke
                event_noMR.append(event_name)
                relaynoMR.append(event_name)
                event11.append(event_name)
            elif event_name[2] in "M":  # it is a medley relay
                stroke.append(event_name)
                if event_name[1] in "L":
                    event11.append(event_name)
                    relaynoMR.append(event_name)
            if event_name[1] in "L":
                relay.append(event_name)

    xvar = LpVariable.dicts('xvar', (athlete, event_noMR), 0, 1, LpBinary)
    yvar = LpVariable.dicts('yvar', (athlete, event_noMR), 0, 1, LpBinary)
    zvar = LpVariable.dicts('zvar', (athlete, event_noMR), 0, 1, LpBinary)

    # Same as above, but the starting leg for the "non-Medley Relay" relays
    xvarstart = LpVariable.dicts('xvarstart', (athlete, relaynoMR), 0, 1, LpBinary)
    yvarstart = LpVariable.dicts('yvarstart', (athlete, relaynoMR), 0, 1, LpBinary)
    zvarstart = LpVariable.dicts('zvarstart', (athlete, relaynoMR), 0, 1, LpBinary)

    # Same ordering as above, but for the athletes assigned to the
    # best, second best, and third best medley relay
    xMRvar = LpVariable.dicts('xMRvar', (athlete, stroke), 0, 1, LpBinary)
    yMRvar = LpVariable.dicts('yMRvar', (athlete, stroke), 0, 1, LpBinary)
    zMRvar = LpVariable.dicts('zMRvar', (athlete, stroke), 0, 1, LpBinary)

    # rvar will hold the TIME of our first, second, and third fastest entrants in each event
    homerank = [1, 2, 3]
    rvar = LpVariable.dicts('rvar', (homerank, event11), None, None, LpContinuous)
    # wvar will be 1 if our athlete with homerank h, in event j, finishes in overall place k, against
    # opponent scenario l
    # with this we can answer in which place our assigned athletes actually finish and score the meet!
    place = [1, 2, 3, 4, 5, 6, 7, 8]
    wvar = LpVariable.dicts('wvar', (event11, homerank, place, scenario), 0, 1, LpBinary)
    # asgnvar is a generic variable which will be 1 if athlete i is assigned to event j (ignoring rank, etc.)
    # just answers the question "Is this athlete doing in this event?"
    asgnvar = LpVariable.dicts('asgnvar', (athlete, event), 0, 1, LpBinary)

    # Objective Function - Maximize the weighted scenario (or expected) score against
    # over eact scenario (or against each team)
    SwimMeetOpt += lpSum(probability_matrix[s] * scenscorevar[s] for s in scenario), "Total Expected Score"
    print("obj done")

    # Multiple relay teams and they cannot sweep so only the top two relay teams are included in the home team score
    # defines the variable scenscorevar (scenario score variable) for each scenario
    indivplcscore = [9, 4, 3, 2, 1, 0, 0, 0]  # NOTE: p starts at val 1, so indivplcscore might start from 9. maybe it was a dict or something? either way this will need to be tweeked.
    relayplcscore = [11, 4, 2, 0, 0, 0, 0, 0]  # NOTE: Same here
    for s in scenario:
        SwimMeetOpt += scenscorevar[s] == (lpSum(
            indivplcscore[p] * wvar[j][k][p][s] for j in indiv for k in homerank for p in place if k <= p) +
                                           lpSum(
                                               relayplcscore[p] * wvar[j][k][p][s] for j in relay for k in homerank for
                                               p in place if k <= p) +
                                           lpSum(2 * wvar[j][1][4][s] - 2 * wvar[j][3][3][s] for j in
                                                 relay)), "Scenario %s Score" % s

    # CREATING THE CONSTRAINTS FOR THE OPTIMIZATION PROBLEM:

    # Exactly one 1st, 2nd, 3rd best time athlete in each indiv event
    # WHAT IF CONCEDE A RACE or a PLACE?
    for j in indiv:
        SwimMeetOpt += lpSum(xvar[i][j] for i in athlete) <= 1, "Exactly one 1st for indiv event %s" % j
        SwimMeetOpt += lpSum(yvar[i][j] for i in athlete) <= 1, "Exactly one 2nd for indiv event %s" % j
        SwimMeetOpt += lpSum(zvar[i][j] for i in athlete) <= 1, "Exactly one 3rd for indiv event %s" % j

    # exactly 4 athletes in a relay for our first, second, and third relays
    # accounting for the opening leg not being a flying start in the non-MR relays
    for j in relaynoMR:
        SwimMeetOpt += lpSum(xvar[i][j] for i in athlete) == RELAY_TEAM_SIZE - 1, "Exactly 4 in 1st relay %s" % j
        SwimMeetOpt += lpSum(yvar[i][j] for i in athlete) == RELAY_TEAM_SIZE - 1, "Exactly 4 in 2nd relay %s" % j
        SwimMeetOpt += lpSum(zvar[i][j] for i in athlete) == RELAY_TEAM_SIZE - 1, "Exactly 4 in 3rd relay %s" % j
        SwimMeetOpt += lpSum(xvarstart[i][j] for i in athlete) == 1, "Exactly 1 to start 1st relay %s" % j
        SwimMeetOpt += lpSum(yvarstart[i][j] for i in athlete) == 1, "Exactly 1 to start 2nd relay %s" % j
        SwimMeetOpt += lpSum(zvarstart[i][j] for i in athlete) == 1, "Exactly 1 to start 3rd relay %s" % j

    # Exactly 4 athletes in the first, second, and third best medley relay
    SwimMeetOpt += lpSum(xMRvar[i][j] for i in athlete for j in stroke) == RELAY_TEAM_SIZE, "Exactly 4 in 1st MR"
    SwimMeetOpt += lpSum(yMRvar[i][j] for i in athlete for j in stroke) == RELAY_TEAM_SIZE, "Exactly 4 in 2nd MR"
    SwimMeetOpt += lpSum(zMRvar[i][j] for i in athlete for j in stroke) == RELAY_TEAM_SIZE, "Exactly 4 in 3rd MR"

    # Athletes in at most Maxevent
    Maxevent = 4
    Maxrelayevent = 3
    Maxindevent = 2
    for i in athlete:
        SwimMeetOpt += lpSum(xvar[i][j] + yvar[i][j] + zvar[i][j] for j in indiv) + lpSum(
            xvar[i][j] + yvar[i][j] + zvar[i][j] + xvarstart[i][j] + yvarstart[i][j] + zvarstart[i][j] for j in
            relaynoMR) + lpSum(
            xMRvar[i][j] + yMRvar[i][j] + zMRvar[i][j] for j in stroke) <= Maxevent, "Max events for athlete %s" % i

    # Athletes in at most Maxrelayevent
    for i in athlete:
        SwimMeetOpt += lpSum(
            xvar[i][j] + yvar[i][j] + zvar[i][j] + xvarstart[i][j] + yvarstart[i][j] + zvarstart[i][j] for j in
            relaynoMR) + lpSum(xMRvar[i][j] + yMRvar[i][j] + zMRvar[i][j] for j in
                               stroke) <= Maxrelayevent, "Max Relay events for athlete %s" % i
        # Athletes in at most Maxindivevent
        SwimMeetOpt += lpSum(
            xvar[i][j] + yvar[i][j] + zvar[i][j] for j in indiv) <= Maxindevent, "Max Indiv events for athlete %s" % i

        # Back to back event constraints
        # HARD CODED WITH EVENT NAMES AND NEEDS TO BE CHECKED
        SwimMeetOpt += xvar[i]["100F"] + yvar[i]["100F"] + zvar[i]["100F"] + xvar[i]["500F"] + yvar[i]["500F"] + \
                       zvar[i]["500F"] <= 1, "No back to back 100F/500F for athlete %s" % i
        SwimMeetOpt += xvar[i]["200F"] + yvar[i]["200F"] + zvar[i]["200F"] + xvar[i]["200IM"] + yvar[i]["200IM"] + \
                       zvar[i]["200IM"] <= 1, "No back to back 200F/200IM for athlete %s" % i
        SwimMeetOpt += xvar[i]["100BS"] + yvar[i]["100BS"] + zvar[i]["100BS"] + xvar[i]["100BR"] + yvar[i]["100BR"] + \
                       zvar[i]["100BR"] <= 1, "No back to back 100BS/100BR for athlete %s" % i

        # Athletes can only be one of the 1st, 2nd, or 3rd ranked atheletes assigned to an event j
        for j in indiv:
            SwimMeetOpt += xvar[i][j] + yvar[i][j] + zvar[i][
                j] <= 1, "athlete %s can only be one of the 1st, 2nd, or 3rd ranked athletes assigned to an event %s" % (
                           i, j)

    # Athletes can only be 1st, 2nd, or 3rd ranked relay team for each relay j
    for i in athlete:
        for j in relaynoMR:
            SwimMeetOpt += xvar[i][j] + yvar[i][j] + zvar[i][j] + xvarstart[i][j] + yvarstart[i][j] + zvarstart[i][
                j] <= 1, "athlete %s can only be one of the 1st, 2nd, or 3rd ranked athletes assigned to a relay event %s" % (
                           i, j)

        # Each athlete can only perform one stroke in medley relay
        SwimMeetOpt += lpSum(xMRvar[i][j] + yMRvar[i][j] + zMRvar[i][j] for j in
                             stroke) <= 1, "Athlete %s can only perform one stroke in medley relay" % i

    # Each stroke on each relay team can only have one athlete assigned
    for j in stroke:
        SwimMeetOpt += lpSum(xMRvar[i][j] for i in athlete) <= 1, "Stroke %s on 1st MR can only have one athlete" % j
        SwimMeetOpt += lpSum(yMRvar[i][j] for i in athlete) <= 1, "Stroke %s on 2nd MR can only have one athlete" % j
        SwimMeetOpt += lpSum(zMRvar[i][j] for i in athlete) <= 1, "Stroke %s on 3rd MR can only have one athlete" % j

    # realized rank of athletes from assignments
    # IF NO RUNNER NEED TO ASSIGN A time larger than the third runner, smaller than the BigM for rank
    # TODO: make a playperf and playperfstart and playperfMR that is a dict and fix the weirdly indexed dicts stuff.
    # TODO: Make it so BigM is a dict where all of the values are double whatever a ghost player's would be (and are ints)
    for j in indiv:
        SwimMeetOpt += rvar[1][j] == lpSum(playperf[i, j] * xvar[i][j] for i in athlete) + 0.5 * BigM[j] + 1.0 - lpSum(
            xvar[i][j] * (0.5 * BigM[j] + 1) for i in athlete)
        SwimMeetOpt += rvar[2][j] == lpSum(playperf[i, j] * yvar[i][j] for i in athlete) + 0.5 * BigM[j] + 2.0 - lpSum(
            yvar[i][j] * (0.5 * BigM[j] + 2) for i in athlete)
        SwimMeetOpt += rvar[3][j] == lpSum(playperf[i, j] * zvar[i][j] for i in athlete) + 0.5 * BigM[j] + 3.0 - lpSum(
            zvar[i][j] * (0.5 * BigM[j] + 3) for i in athlete)

    for j in relaynoMR:
        SwimMeetOpt += rvar[1][j] == lpSum(
            playperf[i, j] * xvar[i][j] + playperfstart[i, j] * xvarstart[i][j] for i in athlete) + RELAY_TEAM_SIZE * 0.5 * \
                       BigM[j] + RELAY_TEAM_SIZE * 1.0 - lpSum(
            (xvar[i][j] + xvarstart[i][j]) * (0.5 * BigM[j] + 1) for i in athlete)
        SwimMeetOpt += rvar[2][j] == lpSum(
            playperf[i, j] * yvar[i][j] + playperfstart[i, j] * yvarstart[i][j] for i in athlete) + RELAY_TEAM_SIZE * 0.5 * \
                       BigM[j] + RELAY_TEAM_SIZE * 2.0 - lpSum(
            (yvar[i][j] + yvarstart[i][j]) * (0.5 * BigM[j] + 2) for i in athlete)
        SwimMeetOpt += rvar[3][j] == lpSum(
            playperf[i, j] * zvar[i][j] + playperfstart[i, j] * zvarstart[i][j] for i in athlete) + RELAY_TEAM_SIZE * 0.5 * \
                       BigM[j] + RELAY_TEAM_SIZE * 3.0 - lpSum(
            (zvar[i][j] + zvarstart[i][j]) * (0.5 * BigM[j] + 3) for i in athlete)

    SwimMeetOpt += rvar[1]["200MR"] == lpSum(
        playperfMR[i, j] * xMRvar[i][j] for i in athlete for j in stroke) + RELAY_TEAM_SIZE * 0.5 * BigM[
                       "200MR"] + RELAY_TEAM_SIZE * 1.0 - lpSum(
        xMRvar[i][j] * (0.5 * BigM["200MR"] + 1) for i in athlete for j in stroke)
    SwimMeetOpt += rvar[2]["200MR"] == lpSum(
        playperfMR[i, j] * yMRvar[i][j] for i in athlete for j in stroke) + RELAY_TEAM_SIZE * 0.5 * BigM[
                       "200MR"] + RELAY_TEAM_SIZE * 2.0 - lpSum(
        yMRvar[i][j] * (0.5 * BigM["200MR"] + 2) for i in athlete for j in stroke)
    SwimMeetOpt += rvar[3]["200MR"] == lpSum(
        playperfMR[i, j] * zMRvar[i][j] for i in athlete for j in stroke) + RELAY_TEAM_SIZE * 0.5 * BigM[
                       "200MR"] + RELAY_TEAM_SIZE * 3.0 - lpSum(
        zMRvar[i][j] * (0.5 * BigM["200MR"] + 2) for i in athlete for j in stroke)

    # force consistency in rank order
    for k in homerank:
        for j in event11:
            if k < TOP_HOME_RANK:
                SwimMeetOpt += rvar[k][j] <= rvar[k + 1][j]

    # runner/team of rank k can be place in at most one place (1st, 2nd, or 3rd) vs opp 1
    for j in indiv:
        for k in homerank:
            for s in scenario:
                SwimMeetOpt += lpSum(wvar[j][k][l][s] for l in place if l >= k) <= 1
    for j in relay:
        for k in homerank:
            for s in scenario:
                SwimMeetOpt += lpSum(wvar[j][k][l][s] for l in place if l >= k) <= 1

    # Did your first runner 1st runner 1st, 2nd in 2nd or 3rd in third vs opp
    # TODO: opptime will either be a dict or list containing a properly formatted pred-perf of all opponent lineups
    TopopprankIndiv = 3  # NOTE: will be a normal constant, the number of opponents assigned to each individual event
    for j in indiv:  # list of individual events (which are all keys)
        for k in homerank:  # [1,2,3]
            for l in place:  # [1,2,3,4,5,6,7,8]
                for s in scenario:  # range(len(opponent_lineup_list))
                    if k == l:
                        SwimMeetOpt += rvar[k][j] <= opptime[1, j, s] * wvar[j][k][l][s] + BigM[j] - BigM[j] * \
                                       wvar[j][k][l][s]
                    if l > k and l < (TopopprankIndiv + k):
                        SwimMeetOpt += rvar[k][j] <= opptime[l - k + 1, j, s] * wvar[j][k][l][s] + BigM[j] - BigM[j] * \
                                       wvar[j][k][l][s]
                    if l > k and l <= (TopopprankIndiv + k):
                        SwimMeetOpt += rvar[k][j] >= opptime[l - k, j, s] * wvar[j][k][l][s]

    # Did your first relay 1st runner 1st, 2nd in 2nd or 3rd in third vs opp
    TopopprankRelay = 3  # NOTE: will be a normal constant, the number of opponents assigned to each relay event
    for j in relay:
        for k in homerank:
            for l in place:
                for s in scenario:
                    if k == l:
                        SwimMeetOpt += rvar[k][j] <= opptime[1, j, s] * wvar[j][k][l][s] + 5 * BigM[j] - 5 * BigM[j] * \
                                       wvar[j][k][l][s]
                    if l > k and l < (TopopprankRelay + k):
                        SwimMeetOpt += rvar[k][j] <= opptime[l - k + 1, j, s] * wvar[j][k][l][s] + 5 * BigM[j] - 5 * \
                                       BigM[j] * wvar[j][k][l][s]
                    if l > k and l <= (TopopprankRelay + k):
                        SwimMeetOpt += rvar[k][j] >= opptime[l - k, j, s] * wvar[j][k][l][s]

    # events assigned to athletes
    for i in athlete:
        for j in event_noMR:
            SwimMeetOpt += asgnvar[i][j] == xvar[i][j] + yvar[i][j] + zvar[i][j]

    # events assigned to athletes
    for i in athlete:
        for j in stroke:
            SwimMeetOpt += asgnvar[i][j] == xMRvar[i][j] + yMRvar[i][j] + zMRvar[i][j]

    # Report the total setup time
    setupStop = time.time()
    print("Total Setup Time = ", int(setupStop - setup_start), " secs")

    # IF YOU WANT TO TEST FOR VORP UNDER VARIOUS SETTINGS UNCOMMENT THIS SECTION

    # #Test indiv athlete for WAR
    # if athletetest != "ALL" and athletetest != "ALL EVENTS" and athletetest in realathlete:
    #     print("Excluding athlete ",athletetest,"!")
    #     for j in indiv:
    #         SwimMeetOpt += xvar[athletetest][j]==0
    #         SwimMeetOpt += yvar[athletetest][j]==0
    #         SwimMeetOpt += zvar[athletetest][j]==0

    #     for j in relaynoMR:
    #         SwimMeetOpt += xvar[athletetest][j]==0
    #         SwimMeetOpt += yvar[athletetest][j]==0
    #         SwimMeetOpt += zvar[athletetest][j]==0
    #         SwimMeetOpt += xvarstart[athletetest][j]==0
    #         SwimMeetOpt += yvarstart[athletetest][j]==0
    #         SwimMeetOpt += zvarstart[athletetest][j]==0

    #     for j in stroke:
    #         SwimMeetOpt += xMRvar[athletetest][j]==0
    #         SwimMeetOpt += yMRvar[athletetest][j]==0
    #         SwimMeetOpt += zMRvar[athletetest][j]==0

    # # The problem data is written to an .lp file
    # SwimMeetOpt.writeLP("SwimMeetOpt.lp")
    # SwimMeetOpt.setSolver(solver)

    # #test team for VORP
    # #add names to these constraints
    # #add a "prob.constraints["constraint name"].addterm(x_3, 10)" to add terms to a constraint
    # #you can remove terms by "prob.constraints["constraint name"].pop(x_1)"
    # #delete constraints by del prob.constraints[constraint_name]
    # #add them as usual
    # #if user wants to find VORP for all then,
    # if athletetest == "ALL":
    #     #loop through all the athletes and add constraints and subtract previous
    #     #constraints (if exist)
    #     print("Excluding ALL athletes sequentially:")
    #     for i in realathlete:
    #         print(" Excluding athlete ",i,"!")

    #         #Add the constraints to exclude the current athlete
    #         print(" Adding constraints for athlete ",i,"!")
    #         for j in indiv:
    #             SwimMeetOpt += xvar[i][j]==0,"indiv xvar excl " + str(j)
    #             SwimMeetOpt += yvar[i][j]==0,"indiv yvar excl " + str(j)
    #             SwimMeetOpt += zvar[i][j]==0,"indiv zvar excl " + str(j)
    #         for j in relaynoMR:
    #             SwimMeetOpt += xvar[i][j]==0, "relaynoMR xvar excl " + str(j)
    #             SwimMeetOpt += yvar[i][j]==0, "relaynoMR yvar excl " + str(j)
    #             SwimMeetOpt += zvar[i][j]==0, "relaynoMR zvar excl " + str(j)
    #             SwimMeetOpt += xvarstart[i][j]==0, "relaynoMR start xvar excl " + str(j)
    #             SwimMeetOpt += yvarstart[i][j]==0, "relaynoMR start yvar excl " + str(j)
    #             SwimMeetOpt += zvarstart[i][j]==0, "relaynoMR start zvar excl " + str(j)
    #         for j in stroke:
    #             SwimMeetOpt += xMRvar[i][j]==0, "relayMR xvar excl " + str(j)
    #             SwimMeetOpt += yMRvar[i][j]==0, "relayMR yvar excl " + str(j)
    #             SwimMeetOpt += zMRvar[i][j]==0, "relayMR zvar excl " + str(j)

    #         # The problem data is written AGAIN to an .lp file
    #         SwimMeetOpt.writeLP("SwimMeetOpt.lp")

    #         #Re-solve the model with "excluding athlete i" constraints above
    #         solveStart = time.time()
    #         SwimMeetOpt.solve()
    #         solveStop = time.time()
    #         #write the new total to the output data structure
    #         ScoreExcludeAthlete[i] = value(SwimMeetOpt.objective)
    #         print(" Total Solve Time = ", int((solveStop - solveStart)/60.0), " mins. without student ",i)
    #         print(" Objective:", value(SwimMeetOpt.objective), " points")

    #         #Delete all the constraints you just added
    #         print(" Delete last athlete's constraints")
    #         for j in indiv:
    #             del SwimMeetOpt.constraints["indiv_xvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["indiv_yvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["indiv_zvar_excl_" + str(j)]
    #         for j in relaynoMR:
    #             del SwimMeetOpt.constraints["relaynoMR_xvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["relaynoMR_yvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["relaynoMR_zvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["relaynoMR_start_xvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["relaynoMR_start_yvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["relaynoMR_start_zvar_excl_" + str(j)]
    #         for j in stroke:
    #             del SwimMeetOpt.constraints["relayMR_xvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["relayMR_yvar_excl_" + str(j)]
    #             del SwimMeetOpt.constraints["relayMR_zvar_excl_" + str(j)]

    # #If all events, the exclude each athlete event pair, solve and report.
    # if athletetest == "ALL EVENTS":
    # loop through all the individual events for each athlete and add constraints and subtract previous
    # constraints (if exist)
    print("Excluding ALL athletes for each EVENT sequentially:")
    for i in realathlete:
        print(" Excluding events for athlete ", i, "!")
        for j in indiv:  # NOTE: EventNoTimeArray is same dict of times that a ghost would have
                         # TODO: make EventNoTimeArray
            if playperf[i, j] != EventNoTimeArray[j]:  # if athlete has a REAL time in this event!
                print(" Excluding event ", j, " for athlete ", i, " and resolving!")
                # Add the constraints to remove the event for the athlete
                SwimMeetOpt += xvar[i][j] == 0, "indiv xvar excl " + str(j)
                SwimMeetOpt += yvar[i][j] == 0, "indiv yvar excl " + str(j)
                SwimMeetOpt += zvar[i][j] == 0, "indiv zvar excl " + str(j)

                # Solve the problem for
                # The problem data is written AGAIN to an .lp file
                SwimMeetOpt.writeLP("SwimMeetOpt.lp")

                # Re-solve the model with "excluding athlete i" constraints above
                solveStart = time.time()
                SwimMeetOpt.solve()
                solveStop = time.time()
                # write the new total to the output data structure
                # TODO: ScoreExcludeAthandEvent is a dict indexed by athlete and indiv event, must create it first, which is why it is having some issues now
                ScoreExcludeAthandEvent[i, j] = value(SwimMeetOpt.objective)  # NOTE: Assume value is a command from gurobi or pulp
                print(" Total Solve Time = ", int((solveStop - solveStart) / 60.0), " mins. without student ", i)
                print(" Objective:", value(SwimMeetOpt.objective), " points")

                # delete the constraints you just made!
                print(" Delete last constraints")
                del SwimMeetOpt.constraints["indiv_xvar_excl_" + str(j)]
                del SwimMeetOpt.constraints["indiv_yvar_excl_" + str(j)]
                del SwimMeetOpt.constraints["indiv_zvar_excl_" + str(j)]
        for j in relaynoMR:
            if playperf[i, j] != EventNoTimeArray[j]:  # if athlete has a REAL time in this event!
                print(" Excluding event ", j, " for athlete ", i, " and resolving!")
                # Add the constraints to remove the event for the athlete
                SwimMeetOpt += xvar[i][j] == 0, "relaynoMR xvar excl " + str(j)
                SwimMeetOpt += yvar[i][j] == 0, "relaynoMR yvar excl " + str(j)
                SwimMeetOpt += zvar[i][j] == 0, "relaynoMR zvar excl " + str(j)
                SwimMeetOpt += xvarstart[i][j] == 0, "relaynoMR start xvar excl " + str(j)
                SwimMeetOpt += yvarstart[i][j] == 0, "relaynoMR start yvar excl " + str(j)
                SwimMeetOpt += zvarstart[i][j] == 0, "relaynoMR start zvar excl " + str(j)

                # Solve the problem for
                # The problem data is written AGAIN to an .lp file
                SwimMeetOpt.writeLP("SwimMeetOpt.lp")

                # Re-solve the model with "excluding athlete i" constraints above
                solveStart = time.time()
                SwimMeetOpt.solve()
                solveStop = time.time()
                # write the new total to the output data structure
                ScoreExcludeAthandEvent[i, j] = value(SwimMeetOpt.objective)
                print(" Total Solve Time = ", int((solveStop - solveStart) / 60.0), " mins. without student ", i)
                print(" Objective:", value(SwimMeetOpt.objective), " points")

                # delete the constraints you just made!
                print(" Delete last constraints")
                del SwimMeetOpt.constraints["relaynoMR_xvar_excl_" + str(j)]
                del SwimMeetOpt.constraints["relaynoMR_yvar_excl_" + str(j)]
                del SwimMeetOpt.constraints["relaynoMR_zvar_excl_" + str(j)]
                del SwimMeetOpt.constraints["relaynoMR_start_xvar_excl_" + str(j)]
                del SwimMeetOpt.constraints["relaynoMR_start_yvar_excl_" + str(j)]
                del SwimMeetOpt.constraints["relaynoMR_start_zvar_excl_" + str(j)]

        # remove the athlete from the MR
        print(" Excluding event MR for athlete ", i, " and resolving!")
        for j in stroke:
            SwimMeetOpt += xMRvar[i][j] == 0, "relayMR xvar excl " + str(j)
            SwimMeetOpt += yMRvar[i][j] == 0, "relayMR yvar excl " + str(j)
            SwimMeetOpt += zMRvar[i][j] == 0, "relayMR zvar excl " + str(j)

        # The problem data is written AGAIN to an .lp file
        SwimMeetOpt.writeLP("SwimMeetOpt.lp")

        # Re-solve the model with "excluding athlete i" from MR constraints above
        solveStart = time.time()
        SwimMeetOpt.solve()
        solveStop = time.time()
        # write the new total to the output data structure
        ScoreExcludeAthandEvent[i, "200MR"] = pulp.value(SwimMeetOpt.objective)  # NOTE: gonna have to make this work somehow...
        print(" Total Solve Time = ", int((solveStop - solveStart) / 60.0), " mins. without student ", i)
        print(" Objective:", pulp.value(SwimMeetOpt.objective), " points")

        # delete the constraints you just made!
        print(" Delete last MR constraints")
        for j in stroke:
            del SwimMeetOpt.constraints["relayMR_xvar_excl_" + str(j)]
            del SwimMeetOpt.constraints["relayMR_yvar_excl_" + str(j)]
            del SwimMeetOpt.constraints["relayMR_zvar_excl_" + str(j)]

            # Solve the WHOLE problem with selected Solver and report it to Excel

########################################################################################################################
#NOTE: not sure why the indent stops here, so I fixed it.
########################################################################################################################
    print("Solve the baseline problem:")
    solveStart = time.time()
    SwimMeetOpt.solve()
    solveStop = time.time()
    print(" Total Solve Time = ", int((solveStop - solveStart) / 60.0), " mins")

    # The status of the solution is printed to the screen
    print(" Status:", LpStatus[SwimMeetOpt.status])
    print(" Objective:", pulp.value(SwimMeetOpt.objective), " points")
    # Return the objective function value for the best feasible soln found
    BestObjective = lpSum(probability_matrix[s] * scenscorevar[s].varValue for s in scenario)
    print(" Best Found Solution Objective= ", BestObjective)

    OptObj = pulp.value(SwimMeetOpt.objective)
    for s in scenario:
        scenscore[s] = scenscorevar[s].varValue  # NOTE: senscore is being SET here and is the expected score while facing the new lineup with other opponent ones
        print(" Score under Scenario ", s, "is ", int(scenscorevar[s].varValue))

    # Each of the variables is printed with it's resolved optimum value
    # NOTE: Look into these more
    for i in athlete:
        for j in event_noMR:
            asgn[i, j] = asgnvar[i][j].varValue
            x[i, j] = xvar[i][j].varValue
            y[i, j] = yvar[i][j].varValue
            z[i, j] = zvar[i][j].varValue
        for j in relaynoMR:
            xstart[i, j] = xvarstart[i][j].varValue
            ystart[i, j] = yvarstart[i][j].varValue
            zstart[i, j] = zvarstart[i][j].varValue
        for j in stroke:
            xMR[i, j] = xMRvar[i][j].varValue
            yMR[i, j] = yMRvar[i][j].varValue
            zMR[i, j] = zMRvar[i][j].varValue

    # output the finishing place of your three entered athletes in each event
    # output array on "4. Assignment and Prediction": HomeAthFinPlace[homerank,event11]
    # w[event11,homerank, place, scenario]
    # NOTE: HomeAthPredTime and HomeAthFinPlace are both OUTPUTS of this function
    for k in homerank:
        for j in event11:
            mins = int(rvar[k][j].varValue / 60)
            secs = rvar[k][j].varValue - mins * 60
            HomeAthPredTime[k, j] = str(mins) + ":" + str(secs)
            for p in place:
                if wvar[j][k][p][1].varValue == 1:
                    HomeAthFinPlace[k, j] = p

                    # if j == "200F":
                    # print("athrank = ",k,", event = ",j,", p = ",p,", w = ", wvar[j][k][p][1].varValue)
    # NOTE: The stuff below looks like it will need bigger changes, to a degree
    # WILL NEED TO BE UPDATED FOR HOW WE WANT TO REPORT THE LINE UP!!

    # HARD CODED Cell locations - to match the worksheet layout on "4. Assignment and Prediction" worksheet
    # This will need to be changed to create more reasonable output. For the research, do we care who does what as long
    # as the scoring is correct and the lineup is "optimal"

    # For each event/relay leg record the athletes the times of athletes that are
    # entered into a list and sort them. Then write to the output arrays.
    # repeat for next event.
    for j in indiv:
        for i in athlete:
            if xvar[i][j].varValue == 1:
                HomeAthAssgnNamesIndiv[1, j] = i
            elif yvar[i][j].varValue == 1:
                HomeAthAssgnNamesIndiv[2, j] = i
            elif zvar[i][j].varValue == 1:
                HomeAthAssgnNamesIndiv[3, j] = i

    for j in relaynoMR:
        xl2 = 2
        xl4 = 2
        yl2 = 2
        yl4 = 2
        zl2 = 2
        zl4 = 2
        for i in athlete:
            if xvarstart[i][j].varValue == 1:
                if j == "200FR":
                    HomeAthAssgnNamesRelay[1, 1] = i
                else:
                    HomeAthAssgnNamesRelay[1, 4] = i
            if yvarstart[i][j].varValue == 1:
                if j == "200FR":
                    HomeAthAssgnNamesRelay[1, 2] = i
                else:
                    HomeAthAssgnNamesRelay[1, 5] = i
            if zvarstart[i][j].varValue == 1:
                if j == "200FR":
                    HomeAthAssgnNamesRelay[1, 3] = i
                else:
                    HomeAthAssgnNamesRelay[1, 6] = i
            if xvar[i][j].varValue == 1:
                if j == "200FR":
                    HomeAthAssgnNamesRelay[xl2, 1] = i
                    xl2 += 1
                else:
                    HomeAthAssgnNamesRelay[xl4, 4] = i
                    xl4 += 1
            if yvar[i][j].varValue == 1:
                if j == "200FR":
                    HomeAthAssgnNamesRelay[yl2, 2] = i
                    yl2 += 1
                else:
                    HomeAthAssgnNamesRelay[yl4, 5] = i
                    yl4 += 1
            if zvar[i][j].varValue == 1:
                if j == "200FR":
                    HomeAthAssgnNamesRelay[zl2, 3] = i
                    zl2 += 1
                else:
                    HomeAthAssgnNamesRelay[zl4, 6] = i
                    zl4 += 1
    l = 1
    for j in stroke:
        for i in athlete:
            if xMRvar[i][j].varValue == 1:
                HomeAthAssgnNamesRelay[l, 7] = i
            if yMRvar[i][j].varValue == 1:
                HomeAthAssgnNamesRelay[l, 8] = i
            if zMRvar[i][j].varValue == 1:
                HomeAthAssgnNamesRelay[l, 9] = i
        l += 1
