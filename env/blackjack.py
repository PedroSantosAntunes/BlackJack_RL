from argparse import Namespace
import os
import tkinter
import logging
from typing import Any

from gui.ui_control import GameUI



from env.lib import (
    Count,
    Action,
    Card,
    Dealer,
    Hand,
    Player,
    Shoe,
    Rules,
    get_starting_hand,
)





N_CARDS_MAX = 11

SHUFFLE_LIMIT = 52 # How many cards left in the shoe before shuffle

class BlackJackEnv:
    def __init__(
        self,
        player: Player,
        dealer: Dealer,
        args: Any,
        ui: GameUI
    ):
        self.player = player
        self.dealer = dealer
        self.cards: list[str] | None = args.cards
        self.dealer_cards: list[str] | None = args.dealer_cards
        self.subset: str | None = args.subset
        self.rules: Rules = args.rules
        self.shoe = Shoe(self.rules.number_of_decks)
        self.active_slot = None
        self._running_count_from_user: int = args.running_count
        self._n_correct_play = 0
        self._n_mistakes = 0
        self._n_rounds = 0
        self.count: Count
        self.legal_actions = [False] * 7
        self.ui = ui


    ###########################
    ### ENVIRONMENT CONTROL ###
    ###########################

    def step(self, action):
        """
        Receives: 
            - action array
            - slot of hand to play
            
        Possible actions:
            - hit
            - stay
            - double
            - insurance
            - split
            - surrender
            - even money

            # TODO maybe change from multiple lists to a list of tuples
            # TODO check slot usage

        Returns:
            - new play state : List[]   if split returns two elements else returns one
            - reward : List[]   if split returns two elements else returns one
            - done : List[]   if split returns two elements else returns one

        """
        logging.info(f"Action: {action.name}\n")
        logging.info(f"STATE: {self.get_play_state()}\n")

        hand = self.get_hand_in_active_slot()

        # TODO if model can input invalid actions check here and return bad reward
        if not self.legal_actions[action.value]:
            print(action)
            print(self.legal_actions)
            return None, None, None, None, False

        # Act on the environment
        # each action should return its reward, payout and done
        match action:
            case Action.SPLIT:
                # Both rewards and hands_done are None because a split cant "close" any hands
                rewards, hands_done = self.split()
                
                new_play_states = [
                    self.get_play_state(),
                    self.get_play_state(split=True),
                ]
                done = self._all_hands_done()

                if not done:
                    self.active_slot = self._get_first_unfinished_hand().slot
                    hand = self.get_hand_in_active_slot()
                    self._update_legal_actions(hand)

                return new_play_states, rewards, hands_done, done, True

            case _:
                action_map = {
                    Action.HIT: self.hit,
                    Action.STAY: self.stay,
                    Action.DOUBLE: self.double,
                    Action.INSURANCE: self.insurance,
                    Action.SURRENDER: self.surrender,
                    Action.EVEN_MONEY: self.even_money,
                }

                reward, hand_done = action_map[action]()

                done = self._all_hands_done()

                new_play_state = [self.get_play_state()]

                if not done:
                    self.active_slot = self._get_first_unfinished_hand().slot
                    hand = self.get_hand_in_active_slot()
                    self._update_legal_actions(hand)

                return [new_play_state,], reward, hand_done, done, True

    # Cleans environment
    def reset(self):
        """Reset button."""
        self.ui.clean_info()
        self.player.buy_in(self.player.initial_stack)
        self.shoe = Shoe(self.rules.number_of_decks)
        self.ui.clean_dealer_slots()
        self.player.init_count()
        self._reset_accuracy()


    def get_count(self):
        return self.player.count

    def get_play_state(self, hand=None, split=False):
        """
        Receives:
            - split to return the last hand created (resultant of the split)

        Returns:
            - sum of revealed dealer cards
            - sum of player cards
            - is_hard (True if no usable Ace, False if hand has a usable Ace)
        
        """
        # get dealer cards sum
        dealer_sum = self.dealer.sum

        # get player cards sum in slot
        if hand:
            player_hand = hand
        elif not split:
            player_hand = self.get_hand_in_active_slot()
        else:
            player_hand = self.get_new_hand()

        return [dealer_sum, player_hand.sum, player_hand.is_hard]    # TEMP

    def get_legal_actions(self):
        return self.legal_actions

    def new_round(self, bet):
        """Starts new round. cleans state for new round"""
        logging.info("Clean for new round!\n")

        self._n_rounds += 1
        self._update_accuracy()

        # Clean UI
        self.ui.new_round()

        self.player.hands = []
        is_end_of_shoe = self.shoe.n_cards < SHUFFLE_LIMIT 
        is_user_given_cards = (
            self.cards is not None
            or self.subset is not None
            or self.dealer_cards is not None
        )
        if self.rules.csm or is_end_of_shoe or is_user_given_cards:
            self.shoe = Shoe(self.rules.number_of_decks)
            self.player.init_count()
        
        # Set running count if given as arguments (for testing and practice purposes)
        if self._running_count_from_user != 0 and self._n_rounds == 1:
            self.player.count.running_count = self._running_count_from_user
        
        if is_end_of_shoe:
            self.ui.animate_shuffle(self.shoe)

        self._deal_starting_cards(bet)

    def _deal_starting_cards(self, bet):
        """
        Returns:
            - hands
            - done - is true when:
                if the player got a blackjack
                if PEEK-RULE and dealer hit blackjack
            
            - reward - if done else NULl
            - payout - if done else NULL
        """
        logging.info("Deal first cards of the round!\n")
        self.bet = bet

        self.ui.fill_discard_tray(self.shoe)  # UI
        hand = self.player.start_new_hand(self.bet)
        self.dealer.init_hand()
        
        if self.dealer_cards:
            self.shoe.arrange(self.dealer_cards)  # DEBUG / TRAIN
        
        # Deal cards to dealer
        self.dealer.deal(self.shoe)
        self.dealer.deal(self.shoe)
        self.dealer.cards[1].visible = False

        self.ui.display_dealer_cards(self.dealer)

        self._handle_counts(self.dealer.cards, self.shoe)
        
        # DEBUG / TRAIN
        if self.cards:
            self.shoe.arrange(self.cards, randomize=True)
        elif self.subset is not None:
            cards = get_starting_hand(self.subset)
            self.shoe.arrange(cards)
        
        # Deal cards to player
        hand.deal(self.shoe)
        hand.deal(self.shoe)
        
        self._handle_counts(hand, self.shoe)
        self.ui.show()
        self.active_slot = hand.slot
        self.ui.display_stack(self.player.stack)
        self.ui.display_chip(hand, 0, self.bet)
        self.ui.display_player_cards(hand)


        # if PEEK-RULE and dealer has blackjack
        dealer_has_blackjack = self._check_dealer_peek()

        # TEMP adapt with logic bellow
        if dealer_has_blackjack:
            if hand.is_blackjack:
                # push (draw)
                pass
            else:
                # lose
                pass

        self._update_legal_actions(hand)
        
        if self.dealer.has_ace:
            if hand.is_blackjack is True:
                self.disable_actions(Action.HIT, Action.DOUBLE)
                self.enable_actions(Action.EVEN_MONEY)
            else:
                self.enable_actions(Action.INSURANCE)
 
        else:
            # TODO check if end hand when black jack or needs to stay
            # if hand.is_blackjack:
            #     self.ui.delayed_ui()
            #     self._end_round()
            #     return
            if self.rules.surrender != "no":
                self.enable_actions(Action.SURRENDER)

        return self.player.hands # TEMP check correct place to return on this method

    def get_round_results(self):
        # reveal dealer hand
        self._reveal_dealer_hidden_card() # TODO check if dealer still reveals hidden card if all hands bust

        # If there are any hands that arent bust or surrender, dealer must play
        self._resolve_dealer_hand()

        # resolve payouts for each hand
        # return list of (reward, payout, new_play_state), one for each hand
        
        return self._round_payout()

    def get_stack_amount(self):
        return self.player.stack

    #############################


    ####################
    ### USER ACTIONS ###
    ####################

    def hit(self):
        """Hit Action
        Returns:
            # TODO update this for only possible outcomes from hit action
            - reward: 
                blackjack = 1.5
                normal win =  1
                push, hand not finished = 0
                surrender = -0,5
                bust / lost -1 

            - hand_done
        """
        ####################
        # Efectuate action #
        ####################

        hand = self.get_hand_in_active_slot()

        self.disable_actions(Action.INSURANCE, Action.SURRENDER)

        # updates hand
        hand.deal(self.shoe)

        self.ui.display_player_cards(hand)

        # Update counts
        self._handle_counts(hand, self.shoe)

        #################
        # Decide reward #
        #################

        reward = 0

        if not hand.is_finished:
            # if good action
                # good reward
            # else:
                # bad reward
            pass


        # Update UI
        if hand.is_over:
            self.ui.hide(hand)
            self.ui.hide_chips(hand)
            self.ui.display_info(hand, "BUST")


        return reward, hand.is_finished


    def stay(self):
        """Stay Action."""

        hand = self.get_hand_in_active_slot()

        hand.is_finished = True
        reward = 0

        return reward, hand.is_finished


    def double(self):
        """Double Action (doubles the bet amount and only receives one more card)."""

        hand = self.get_hand_in_active_slot()

        self.disable_actions(Action.INSURANCE, Action.SURRENDER)

        self.player.stack -= self.bet
        hand.bet += self.bet
        hand.deal(self.shoe)
        hand.is_finished = True
        self._handle_counts(hand, self.shoe)
        
        self.ui.display_stack(self.player.stack)
        self.ui.display_chip(hand, 1, self.bet)
        self.ui.display_player_cards(hand, rotate_last=True)

        reward = 0
        # TODO remove reward from all actions ??

        # Update UI
        if hand.is_over:
            self.ui.hide(hand)
            self.ui.hide_chips(hand)
            self.ui.display_info(hand, "BUST")

        return reward, hand.is_finished


    def insurance(self):
        """Insurance Action."""

        hand = self.get_hand_in_active_slot()
        self.dealer.insurance_bet = hand.bet / 2
        self.player.stack -= self.dealer.insurance_bet
        self.disable_actions(Action.INSURANCE, Action.SURRENDER)
        
        self.ui.display_insurance_chip(self.dealer.insurance_bet)
        self.ui.display_stack(self.player.stack)

        reward = 0

        return reward, hand.is_finished


    def split(self):
        """Split Action."""
        hand = self.get_hand_in_active_slot()

        self.disable_actions(Action.SURRENDER, Action.INSURANCE)

        new_hand = self.player.start_new_hand(self.bet)
        split_card = hand.cards.pop()
        new_hand.deal(split_card)
        
        self.ui.display_chip(new_hand, 0, self.bet)
        self.ui.display_stack(self.player.stack)

        for split_hand in (hand, new_hand):
            split_hand.is_split_hand = True
            split_hand.deal(self.shoe)
            if split_hand.cards[0].label == "A":
                # Split Aces receive only one card more
                split_hand.is_hittable = False
                if split_hand.cards[1].label != "A":
                    split_hand.is_finished = True
                if (
                    split_hand.cards[1].label == "A"
                    and not self.rules.resplit_aces
                ):
                    split_hand.is_finished = True

        self.player.sort_hands()

        for h in self.player.hands:
            two_aces = h.cards[0].label == "A" and h.cards[1].label == "A"
            if two_aces and len(self.player.hands) == 4:
                h.is_finished = True
            
            self._handle_counts(h, self.shoe)

            # UI
            self.ui.display_player_cards_rotate(h)

        return None, None


    def surrender(self):
        """Surrender Action."""

        hand = self.get_hand_in_active_slot()
        hand.is_finished = True
        hand.surrender = True

        self.ui.display_stack(self.player.stack)
        self.ui.delayed_ui()
        self.ui.hide(hand)
        self.ui.hide_chips(hand)
        self.ui.display_info(hand, "SURRENDER")

        reward = 0

        return reward, hand.is_finished


    def even_money(self):
        """Even Money Action (if hand is blackjack and dealer shows ace get paid 1:1)"""
        
        hand = self.get_hand_in_active_slot()
        self.dealer.even_money = True

        self.ui.hide(hand)

        reward = None # TODO rewards are all being treated at the end of a round

        return reward, hand.is_finished

    ######################


    def _all_hands_done(self) -> bool:
        return self.player.all_hands_done()



    # # Called by split and every other action
    # def _resolve_next_hand(self):
    #     hand = self._get_first_unfinished_hand()
    #     # if hand is not None:
    #     #     self.active_slot = hand.slot
    #     #     self._update_legal_actions(hand)
    #     #     self.ui.display_finger(hand)
    #     # else:
    #     self.ui.clean_info()
    #     self.ui.hide_fingers()

    #     # If not all hands lost or there is insurance
    #     # Outcome depends on the dealer hand
    #     if not self._is_all_over() or self.dealer.insurance_bet > 0:
    #         self.ui.delayed_ui()
    #         self._reveal_dealer_hidden_card()
    #     else:
    #         self._handle_counts(self.dealer.cards, self.shoe)
    #         self._payout()


    def _reveal_dealer_hidden_card(self):
        self.ui.display_dealer_cards(self.dealer, hide_second=False)
        self.dealer.cards[1].visible = True
        self._handle_counts(self.dealer.cards, self.shoe)


    def _resolve_dealer_hand(self):
        # UI
        if self.dealer.is_blackjack and self.dealer.insurance_bet > 0:
            self.ui.display_insurance_chip(self.dealer.insurance_bet, triple=True)
        else:
            self.ui.hide_insurance_chip()

        # If all player hands are either:
        #   - black jack
        #   - surrender
        #   - bust

        # Dealer doesnt draw more cards
        
        # Check if dealer was already finished
        if not self.dealer.is_finished:
            self.dealer.is_finished = True

            for hand in self.player.hands:
                if not (hand.is_blackjack or hand.is_over or hand.surrender):
                    self.dealer.is_finished = False


        if not self.dealer.is_finished:
            self.ui.delayed_ui()
            self._dealer_draw_cards()
        else:
            self._handle_counts(self.dealer.cards, self.shoe)


    def _dealer_draw_cards(self):
        """Dealer keeps drawing cards until its hand is finished (bust, above 17)"""
        self.dealer.deal(self.shoe)
        self.ui.display_dealer_cards(self.dealer)
        self._handle_counts(self.dealer.cards, self.shoe)
        if not self.dealer.is_finished:
            self.ui.delayed_ui()
            self._dealer_draw_cards()
        else:
            self._handle_counts(self.dealer.cards, self.shoe)


    def _round_payout(self):
        self.ui.hide_fingers()

        hand_results = []

        for hand in self.player.hands:
            hand_reward = 0
            hand_profit = 0
            hand_new_state = None

            result = ""

            

            # Insurance
            if (
                self.dealer.insurance_bet > 0
            ):
                if (self.dealer.is_blackjack):
                    hand_reward += 1
                    hand_profit += self.dealer.insurance_bet * 2

                    self.player.stack += self.dealer.insurance_bet * 3
                    self.ui.display_insurance_chip(self.dealer.insurance_bet, triple=True)
                    result = "INSURANCE"

                else:
                    hand_reward -= 0.5
                    hand_profit -= self.dealer.insurance_bet

            # Surrender
            if (hand.surrender):
                hand_reward -= 0.5
                hand_profit -= hand.bet / 2

                self.player.stack += self.bet / 2
                self.ui.hide_chips(hand)
                result += "SURRENDER"

            # Even Money
            elif self.dealer.even_money is True:
                hand_reward += 1
                hand_profit += hand.bet * 1

                self.player.stack += hand.bet * 2
                result = "EVEN MONEY"
                self.ui.display_chips(hand, self.bet)

            # Triple Seven
            elif hand.is_triple_seven is True:
                hand_reward += 2
                hand_profit += hand.bet * 2

                self.player.stack += hand.bet * 3
                if result == "INSURANCE":
                    result += " + "
                result += "TRIPLE SEVEN"
                if hand.bet == 2 * self.bet:
                    self.bet = hand.bet
                self.ui.display_chips(hand, self.bet, triple=True)

            # Player has blackjack
            # Dealer doesnt have blackjack
            elif (
                hand.is_blackjack is True and self.dealer.is_blackjack is False
            ):
                hand_reward += 1.5
                hand_profit += hand.bet * 1.5

                self.player.stack += hand.bet * 2.5
                result = "BLACKJACK"
                self.ui.display_chips(hand, self.bet, bj=True)
            
            # Player and Dealer have blackjack
            elif hand.is_blackjack is True and self.dealer.is_blackjack is True:
                hand_reward += 0
                hand_profit += 0

                self.player.stack += hand.bet
                result = "PUSH"

            # Player doesnt have blackjack
            # Dealer has blackjack
            elif (
                self.dealer.is_blackjack is True
                and hand.is_blackjack is False
                and hand.is_over is False
            ):
                hand_reward -= 1
                hand_profit -= hand.bet

                self.ui.dealer_info("BLACKJACK")
                result = "LOSE"
                self._resolve_lost_hand(hand)

            # Player didnt bust
            # Dealer bust
            elif hand.is_over is False and self.dealer.is_over is True:
                hand_reward += 1
                hand_profit += hand.bet * 1
                
                self.ui.dealer_info("BUST")
                self.player.stack += hand.bet * 2
                result = "WIN"
                self.ui.display_chips(hand, self.bet)


            # Player bust
            elif hand.is_over is True:
                hand_reward -= 1
                hand_profit -= hand.bet * 1

                result = "BUST"
                self._resolve_lost_hand(hand)

            # Player hand less than Dealer hand
            elif hand.sum < self.dealer.sum:
                hand_reward -= 1
                hand_profit -= hand.bet * 1

                result = f"LOSE ({hand.sum} vs {self.dealer.sum})"
                self._resolve_lost_hand(hand)

            # Player hand greater than Dealer hand
            elif hand.sum > self.dealer.sum:
                hand_reward += 1
                hand_profit += hand.bet * 1

                self.player.stack += hand.bet * 2
                result = f"WIN ({hand.sum} vs {self.dealer.sum})"
                self.ui.display_chips(hand, self.bet)

            # Player hand equal to Dealer hand
            elif hand.sum == self.dealer.sum:
                hand_reward += 0
                hand_profit += 0

                self.player.stack += hand.bet
                result = "PUSH"

            else:
                raise ValueError

            self.ui.display_info(hand, result)
            self.ui.display_stack(self.player.stack)
            hand_new_state = self.get_play_state(hand)
            hand_results += [(hand_new_state, hand_reward, hand_profit)]

        return hand_results

    def _handle_counts(self, hand: Hand | list[Card], shoe: Shoe):
        """Update counts"""
        self.player.update_counts(hand, shoe)


    def _resolve_lost_hand(self, hand: Hand):
        self.ui.hide_chips(hand)
        self.ui.hide(hand)
        hand.bet = 0

    def _check_dealer_peek(self) -> bool:
        if self.rules.peek and self.dealer.is_blackjack:
            self.ui.delayed_ui()
            self._reveal_dealer_hidden_card()
            return True
        return False

    def _update_legal_actions(self, hand: Hand):
        n_hands = len(self.player.hands)
        
        # Can double
        if (
            len(hand.cards) == 2
            and hand.is_hittable is True
            and not (hand.is_split_hand and not self.rules.double_after_split)
            and not hand.played
        ):
            self.enable_actions(Action.DOUBLE)
        else:
            self.disable_actions(Action.DOUBLE)
        
        # Can split
        if (
            hand.cards[0].value == hand.cards[1].value
            and len(hand.cards) == 2
            and n_hands < 4
        ):
            self.enable_actions(Action.SPLIT)
        else:
            self.disable_actions(Action.SPLIT)

        # Can hit or stay
        if hand.is_hittable is True:
            self.enable_actions(Action.HIT, Action.STAY)
        else:
            self.disable_actions(Action.HIT, Action.STAY)


        if hand.is_split_hand and hand.cards[0].label == "A":
            self.enable_actions(Action.STAY)

        # Can split double aces
        if (
            hand.is_split_hand
            and hand.cards[0].label == "A"
            and hand.cards[1].label == "A"
            and not self.rules.resplit_aces
        ):
            self.disable_actions(Action.SPLIT)



    def enable_actions(self, *actions):
        for action in actions:
            self.legal_actions[action.value] = True

    def disable_actions(self, *actions):
        for action in actions:
            self.legal_actions[action.value] = False

    def _update_accuracy(self):
        n_decisions = self._n_correct_play + self._n_mistakes
        if n_decisions != 0:
            txt = f"Accuracy: {round(self._n_correct_play / (self._n_correct_play + self._n_mistakes) * 100, 2)}%"
        else:
            txt = "Accuracy: 0%"
        txt += f"\nRounds: {self._n_rounds}"

    def _check_insurance(self, hand: Hand) -> bool:
        if self.player.count.true_count < 3:
            self.ui.display_info(hand, "Try again!")
            self.ui.delayed_ui()
            self.ui.clean_info()
            return False
        return True

    def _is_all_over(self) -> bool:
        for hand in self.player.hands:
            if hand.is_over is False and hand.surrender is False:
                return False
        return True

    def _get_first_unfinished_hand(self) -> Hand | None:
        for hand in self.player.hands:
            if hand.is_finished is False:
                return hand
        return None

    def get_hand_in_active_slot(self) -> Hand:
        for hand in self.player.hands:
            if hand.slot == self.active_slot:
                return hand
        raise RuntimeError

    def get_new_hand(self):
        """Get new hand created"""
        return self.player.hands[-1]

    def _reset_accuracy(self):
        self._n_correct_play = 0
        self._n_mistakes = 0
        self._n_rounds = 0





def start_env(args: Namespace) -> BlackJackEnv:
    logging.basicConfig(level=args.loglevel)
    logging.info("Game started!\n")
    ui = GameUI(args.rules, N_CARDS_MAX, "#4e9572")
    dealer = Dealer(args.rules.game_type)
    player = Player(
        rules=args.rules,
        stack=args.stack,
    )

    game = BlackJackEnv(player, dealer, args, ui)
    game.reset()
    game.ui.root.update()

    return game