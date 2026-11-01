from app.voting.rules import choose_winner

def test_ties_use_canonical_venue_id_and_zero_turnout_cancels():
    options=[{'itemId':'B','venueId':'venue-z'},{'itemId':'A','venueId':'venue-a'}]
    ballots=[{'choiceItemId':'A'},{'choiceItemId':'B'}]
    assert choose_winner(options,ballots)==('A',{'B':1,'A':1})
    assert choose_winner(list(reversed(options)),ballots)[0]=='A'
    assert choose_winner(options,[])[0] is None
