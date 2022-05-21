import typing as T


LOOTING_GROUP_NUM = 0
MINING_GROUP_NUM = LOOTING_GROUP_NUM + 50
INACTIVE_GROUP_NUM = -1
TEAMS_PER_GROUP = 6
CRABS_PER_GROUP = 2


def assign_teams_to_groups(teams_info: T.Dict[int, T.Tuple[int, int]]) -> T.Dict[int, int]:
    team_assignments = {}
    fast_mine_teams = []
    slow_mine_teams = []
    for team, info in teams_info.items():
        group, mp = info
        if group in [LOOTING_GROUP_NUM, INACTIVE_GROUP_NUM]:
            team_assignments[team] = group
            continue

        if mp >= 231:
            fast_mine_teams.append(team)
        else:
            slow_mine_teams.append(team)

    group = MINING_GROUP_NUM
    num_teams = 0

    for teams in [fast_mine_teams, slow_mine_teams]:
        for team in teams:
            num_teams += 1
            team_assignments[team] = group
            if num_teams > TEAMS_PER_GROUP:
                num_teams = 0
                group += 1
    return team_assignments


def assign_crabs_to_groups(crabs: T.List[int], groups: T.List[int]) -> T.Dict[int, int]:
    crab_assignments = {}
    num_crabs = 0
    group_inx = 0
    for crab in crabs:
        num_crabs += 1
        crab_assignments[crab] = groups[group_inx]
        if num_crabs > CRABS_PER_GROUP:
            num_crabs = 0
    return crab_assignments
