import argparse
import numpy
import pandas as pd
import re
import requests
from bs4 import BeautifulSoup
from conferences import CONFERENCES
from common import differential_vector, find_name_from_nickname
from constants import YEAR
from datetime import datetime
from predictor import Predictor
from teams import TEAMS


AWAY = 1
HOME = 0
TEAM_NAME_REGEX = 'schools/.*?/%s.html' % YEAR


def read_team_stats_file(team_filename):
    return pd.read_csv(team_filename)


def convert_team_totals_to_averages(stats):
    fields_to_average = ['mp', 'fg', 'fga', 'fg2', 'fg2a', 'fg3', 'fg3a', 'ft',
                         'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov',
                         'pf']
    num_games = stats['g']
    new_stats = stats.copy()

    for field in fields_to_average:
        new_value = float(stats[field]) / num_games
        new_stats.loc[:,field] = new_value
    return new_stats


def extract_stats_components(stats, away=False):
    # Get all of the stats that don't start with 'opp', AKA all of the
    # stats that are directly related to the indicated team.
    filtered_columns = [col for col in stats if not str(col).startswith('opp')]
    stats = stats[filtered_columns]
    stats = convert_team_totals_to_averages(stats)
    if away:
        # Prepend all stats with 'opp_' to signify the away team as such.
        away_columns = ['opp_%s' % col for col in stats]
        stats.columns = away_columns
    return stats


def get_totals(games_list, predictions, team_wins):
    for i in range(0, len(games_list)):
        winner = games_list[i][predictions[i]]
        team_wins[winner] += 1
    return team_wins


def teams_list(conference):
    if not conference:
        teams = TEAMS.values()
    else:
        teams = CONFERENCES[conference]
    return teams


def split_datasets(dataset, set_size):
    for i in xrange(0, len(dataset), set_size):
        yield dataset[i:i+set_size]


def initialize_team_wins(teams):
    team_wins = {}

    for team in teams:
        team_wins[team] = 0
    return team_wins


def predict_all_matches(predictor, stats_dict, teams):
    fields_to_rename = {'win_loss_pct': 'win_pct',
                        'opp_win_loss_pct': 'opp_win_pct'}
    team_wins = initialize_team_wins(teams)

    for dataset in split_datasets(teams, 75):
        games_list = []
        prediction_stats = pd.DataFrame()
        match_stats = []
        for home_team in dataset:
            team_wins[home_team] = 0
            print home_team
            for away_team in teams:
                if home_team == away_team:
                    continue
                home_stats = stats_dict[home_team]
                away_stats = stats_dict['%s_away' % away_team]
                match_stats.append(pd.concat([away_stats, home_stats], axis=1))
                games_list.append([home_team, away_team])
        prediction_stats = pd.concat(match_stats)
        match_vector = differential_vector(prediction_stats)
        match_vector.rename(columns=fields_to_rename, inplace=True)
        match_stats_simplified = predictor.simplify(match_vector)
        predictions = predictor.predict(match_stats_simplified, int)
        team_wins = get_totals(games_list, predictions, team_wins)
    return team_wins


def create_stats_dictionary(teams):
    stats_dict = {}

    for team in teams:
        stats = read_team_stats_file('team-stats/%s' % team)
        home_stats = extract_stats_components(stats)
        away_stats = extract_stats_components(stats, away=True)
        stats_dict[team] = home_stats
        stats_dict['%s_away' % team] = away_stats
    return stats_dict


def print_rankings(team_wins):
    i = 1

    sorted_ranks = [(v,k) for k,v in team_wins.iteritems()]
    sorted_ranks.sort(reverse=True)
    for wins, team in sorted_ranks:
        team = find_name_from_nickname(team)
        print '%s. %s: %s' % (str(i).rjust(3), team, wins)
        i += 1


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--conference', help='Optionally specify a particular '
    'conference to analyze the power rankings for. For example, specify "Big '
    'Ten Conference" to get power rankings only comprising the Big Ten teams.',
    default=None)
    return parser.parse_args()


def main():
    args = parse_arguments()
    predictor = Predictor()
    teams = teams_list(args.conference)
    stats_dict = create_stats_dictionary(teams)
    team_wins = predict_all_matches(predictor, stats_dict, teams)
    print_rankings(team_wins)


if __name__ == "__main__":
    main()
