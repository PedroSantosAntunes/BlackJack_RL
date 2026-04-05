from dataclasses import dataclass
import random
import tkinter
from typing import List, Literal

@dataclass
class Rules:
    game_type: Literal["s17", "h17"]
    surrender: Literal["no", "2-10"]
    peek: bool
    double_after_split: bool = True
    resplit_aces: bool = True
    triple_seven: bool = False
    region: Literal["US", "Europe", "Helsinki"] = "US"
    number_of_decks: int = 6
    csm: bool = False


@dataclass
class Count:
    running_count: int
    true_count: float

# Card that holds label, suit and value
class Card:
    def __init__(self, label: str, suit: str, visible: bool = True):
        self.label = label
        self.suit = suit
        self.value = self._get_value()
        self.visible = visible
        self.counted = False

    def _get_value(self) -> int | tuple:
        if self.label in ("2", "3", "4", "5", "6", "7", "8", "9", "10"):
            return int(self.label)
        if self.label in ("J", "Q", "K"):
            return 10
        if self.label == "A":
            return 1, 11
        raise ValueError("Bad label")

    def __repr__(self) -> str:
        if self.suit == "spades":
            suit = "\u2660"
        elif self.suit == "clubs":
            suit = "\u2663"
        elif self.suit == "diamonds":
            suit = "\u2666"
        elif self.suit == "hearts":
            suit = "\u2665"
        else:
            raise ValueError("Bad suit")
        return f"{self.label}{suit}"

# Deck with 52 cards
class Deck:
    def __init__(self):
        self.cards = []
        self._build()

    def _build(self):
        for suit in ["spades", "clubs", "diamonds", "hearts"]:
            for v in (
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
                "J",
                "Q",
                "K",
                "A",
            ):
                self.cards.append(Card(v, suit))

# Set of multiple decks from where the Dealer takes cards
class Shoe:
    def __init__(self, n_decs: int):
        self.cards: List[Card] = []
        self.n_cards = 0
        self.n_decs = n_decs
        self._n_cards_total = self.n_decs * 52
        self._build()

    # Creates N number of decks and shuffles them
    def _build(self):
        for _ in range(self.n_decs):
            deck = Deck()
            for card in deck.cards:
                self.cards.append(card)
        random.shuffle(self.cards)
        self.n_cards = len(self.cards)

    # Gets the first card on the shoe and removes it
    def draw(self) -> Card:
        """Draws a card from shoe."""
        if self.n_cards > 0:
            card = self.cards.pop(0)
            self.n_cards -= 1
            return card
        raise ValueError("Empty shoe!")

    # Used to display amount of cards in shoe in relation to the initial state
    def fill_discard_tray(self, progress: tkinter.Label) -> None:
        fraction = (self._n_cards_total - self.n_cards) / self._n_cards_total
        y = self.n_decs * 20
        if progress is not None:
            progress.place(
                x=30, y=y, anchor="se", relheight=fraction, relwidth=1.0
            )

    # For debugging and training purpusues only
    def arrange(self, cards: list[str], randomize: bool = False):
        """Arranges shoe so that next cards are the requested ones."""
        if ";" in str(cards):
            # Choose one hand randomly from input like --cards="A,7;7,7;10,10"
            options = [
                [cards[i].split(";")[-1], cards[i + 1].split(";")[0]]
                for i in range(len(cards) - 1)
            ]
            cards = random.choice(options)

        labels = [card.label for card in self.cards]
        if randomize and len(cards) > 1:
            # randomize the first two cards
            cards = random.sample(cards[0:2], 2) + cards[2:]
        for ind, card in enumerate(cards):
            indices = [i for i, x in enumerate(labels[ind:]) if x == str(card)]
            shoe_ind = random.choice(indices) + ind
            self.cards[shoe_ind], self.cards[ind] = (
                self.cards[ind],
                self.cards[shoe_ind],
            )
            labels[shoe_ind], labels[ind] = labels[ind], labels[shoe_ind]

# Contains:
# - set of cards 
# - possbile actions for that hand
# - bet amount
class Hand:
    def __init__(self, rules: Rules):
        self.rules = rules
        self.cards: list[Card] = []
        self.sum: float = 0.0
        self.bet: int = 0
        self.is_hard: bool = True
        self.is_hittable: bool = True  # if True, can receive more cards
        self.is_blackjack: bool = False
        self.is_over: bool = False
        self.surrender: bool = False
        self.is_asked_to_split: bool = False
        self.is_split_hand: bool = False
        self.slot = None
        self.is_finished: bool = False  # if True, no more playing for this hand
        self.played: bool = False
        self.is_triple_seven: bool = False
        self.is_allowed_to_split: bool = True  # if False, can't split this hand
        self.is_pair: bool = False

    def deal(
        self,
        source: Shoe | Card,
    ):
        if isinstance(source, Shoe):
            self.cards.append(source.draw())
        else:
            self.cards.append(source)
        self.sum, self.is_hard = evaluate_hand(self.cards)

        if len(self.cards) == 2 and self.cards[0].value == self.cards[1].value:
            self.is_pair = True
        else:
            self.is_pair = False

        if (
            len(self.cards) == 3
            and all(card.label == "7" for card in self.cards)
            and not self.is_split_hand
            and self.rules.triple_seven
        ):
            self.is_triple_seven = True
            self.is_finished = True
            self.is_hittable = False
        if self.sum >= 22:
            self.is_finished = True
            self.is_hittable = False
            self.is_over = True
        if self.sum == 21 and len(self.cards) == 2 and not self.is_split_hand:
            self.is_blackjack = True

    def __repr__(self) -> str:
        return format_hand(self.cards)


# Acts like a player and fetchs cards from the shoe
class Dealer:
    def __init__(self, game_type: Literal["h17", "s17"]):
        self.game_type = game_type
        self.cards: list[Card] = []
        self.sum: float = 0.0
        self.is_blackjack: bool = False
        self.is_finished: bool = False
        self.is_over: bool = False
        self.insurance_bet = 0.0
        self.even_money: bool = False
        self.has_ace: bool = False

    def init_hand(self):
        self.cards = []
        self.sum = 0
        self.is_blackjack = False
        self.is_finished = False
        self.is_over = False
        self.insurance_bet = 0
        self.even_money = False

    def deal(self, shoe: Shoe):
        card = shoe.draw()
        self.cards.append(card)
        self.sum, is_hard = evaluate_hand(self.cards)
        self.has_ace = self.cards[0].label == "A"
        if self.sum == 17:
            if self.game_type == "s17":
                self.is_finished = True
            if self.game_type == "h17":
                self.is_finished = is_hard
        elif self.sum > 17:
            self.is_finished = True
        if self.sum == 21 and len(self.cards) == 2:
            self.is_blackjack = True
        if self.sum > 21:
            self.is_over = True

    def __repr__(self) -> str:
        return format_hand(self.cards)


class Player:
    def __init__(self, rules: Rules, stack: float = 1000):
        self.rules = rules
        self.stack = stack  # Amount of money player has
        self.hands: List[Hand] = []
        self.initial_stack = stack
        self.invested = 0.0
        self.count = Count(0, 0.0)  # Only feed true count to model

    def buy_in(self, bet: float):
        self.stack = bet

    def start_new_hand(self, bet: int) -> Hand:
        hand = Hand(self.rules)
        hand.bet = bet
        self.stack -= bet
        self.invested += bet
        hand.slot = self._get_next_free_slot()
        self.hands.append(hand)
        return hand

    def sort_hands(self):
        self.hands.sort(key=lambda x: x.slot)  # type: ignore

    def _get_next_free_slot(self):
        n_hands = len(self.hands)
        if n_hands == 0:
            return 2
        if n_hands == 1:
            return 1
        if n_hands == 2:
            return 3
        if n_hands == 3:
            return 0
        raise RuntimeError("Too many hands")

    def init_count(self):
        self.count.running_count = 0
        self.count.true_count = 0.0

    def update_counts(self, hand: Hand | list[Card], shoe: Shoe):
        cards = hand.cards if isinstance(hand, Hand) else hand
        for card in cards:
            self._update_running_count(card)
            self._update_true_count(shoe)

    def _update_true_count(self, shoe: Shoe):
        n_decs_left = shoe.n_cards / 52
        self.count.true_count = self.count.running_count / n_decs_left

    def _update_running_count(self, card: Card):
        if not card.visible or card.counted:
            return
        if card.label == "A" or card.value == 10:
            self.count.running_count -= 1
        elif isinstance(card.value, int) and card.value <= 6:
            self.count.running_count += 1
        card.counted = True

# Calculates the hand value and if the hand is hard (has an Ace counted as 11)
def evaluate_hand(cards: list) -> tuple:
    the_sum = 0
    ace_used = False
    is_hard = True
    for card in cards:
        if card.label == "A":
            is_hard = False
            if not ace_used:
                the_sum += 11
                ace_used = True
            else:
                the_sum += 1
        else:
            if isinstance(card.value, int):
                the_sum += card.value
    if the_sum > 21:
        the_sum = 0
        is_hard = True
        for card in cards:
            if card.label == "A":
                the_sum += 1
            else:
                if isinstance(card.value, int):
                    the_sum += card.value
    return the_sum, is_hard


def format_hand(cards: list) -> str:
    return str(cards)[1:-1].replace(",", " ") + " "


def get_rules(region: Literal["US", "Europe", "Helsinki"]):
    if region == "US":
        rules = Rules(
            game_type="h17",
            surrender="no",
            peek=True,
            resplit_aces=False,
        )
    if region == "Europe":
        rules = Rules(
            game_type="s17",
            surrender="no",
            peek=False,
        )
    if region == "Helsinki":
        rules = Rules(
            game_type="s17",
            surrender="2-10",
            peek=False,
            triple_seven=True,
        )
    rules.region = region
    return rules

