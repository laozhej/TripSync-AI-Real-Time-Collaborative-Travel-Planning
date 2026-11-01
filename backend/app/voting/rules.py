"""Pure turnout/tie rule; authorization and deadlines belong to the service."""
def choose_winner(options,ballots):
    counts={o['itemId']:sum(b['choiceItemId']==o['itemId'] for b in ballots) for o in options}
    winner=min(options,key=lambda o:(-counts[o['itemId']],o['venueId']))['itemId'] if ballots else None
    return winner,counts
