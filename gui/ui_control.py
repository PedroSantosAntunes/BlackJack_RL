import tkinter
import time
from .settings import set_window_position
from env.lib import Shoe, Hand, Dealer, Rules
from .table_components import TableComponents
from PIL import Image, ImageTk
import os

TIME_DELAY = 0
IMG_PATH = f"{os.path.dirname(__file__)}/images/"

class GameUI:
    def __init__(
        self,
        rules : Rules,
        n_cards_max,
        background,
    ):
        self.root = tkinter.Tk()
        set_window_position(self.root, 900, 700)
        self.background = background
        self.n_cards_max = n_cards_max
        self.rules = rules
        self.img_path = IMG_PATH
        self.components = self.start_components()
        self.set_description()

    def start_components(self):
        components = TableComponents(self.root, self.background, self.img_path)
        components.setup_canvas()
        components.get_shoe_progress(self.rules.number_of_decks)
        components.get_label()
        components.get_dealer_info()
        components.get_info()
        components.get_finger()
        components.get_player_slots(self.n_cards_max)
        components.get_chips()
        components.get_dealer_slot()
        components.get_insurance_chip()
        components.get_shuffle_indicator()
        return components
    
    def set_description(self):
        description = "H17" if self.rules.game_type == "h17" else "S17"
        description += f", {self.rules.number_of_decks} decks"
        if self.rules.peek:
            description += ", Dealer peek"
        else:
            description += ", No dealer peek"
        if self.rules.surrender != "no":
            description += ", Surrender"
        if self.rules.double_after_split:
            description += ", DAS"
        if self.rules.resplit_aces:
            description += ", RSA"
        if self.rules.triple_seven:
            description += ", 7-7-7 pays 3:1"
        self.root.title(f"Blackjack - {description}")
        self.root.configure(background=self.background)


    def new_round(self):
        self.clean_info()
        self.clean_dealer_slots()
        self.hide_all_chips()
        self.hide_insurance_chip()
        self.hide_fingers()
        self._clean_player_slots()
        self.dealer_info()
        self.root.update()


    ###########
    ## Cards ##
    ###########

    def show(self):
        """[UI]"""
        for slot in range(4):
            for n in range(self.n_cards_max):
                self.components.slot_player[f"{str(slot)}{str(n)}"].configure(
                    state=tkinter.NORMAL
                )
        self.root.update()

    def hide(self, hand: Hand):
        """[UI]"""
        for n in range(self.n_cards_max):
            self.components.slot_player[f"{str(hand.slot)}{str(n)}"].configure(
                state=tkinter.DISABLED
            )
        self.root.update()

    def _clean_player_slots(self):
        """[UI]"""
        for slot in range(4):
            for n in range(self.n_cards_max):
                self.components.slot_player[f"{str(slot)}{str(n)}"].configure(
                    image="", width=0, height=0
                )
        self.root.update()

    def clean_dealer_slots(self):
        """[UI]"""
        for pos in self.components.slot_dealer.values():
            pos.configure(image="", width=0)
        self.root.update()


    def display_dealer_cards(self, dealer: Dealer, hide_second: bool = True):
        """[UI]"""
        for ind, card in enumerate(dealer.cards):
            if ind == 1 and hide_second is True and len(dealer.cards) == 2:
                img, width, _ = self.components.get_image()
            else:
                img, width, _ = self.components.get_image(card)
            self.components.slot_dealer[str(ind)].configure(
                image=img, width=width
            )
            self.components.slot_dealer[str(ind)].image = img  # type: ignore

        self.root.update()
        self.delayed_ui()

    def display_player_cards(self, hand: Hand, rotate_last: bool = False):
        """[UI]"""
        for ind, card in enumerate(hand.cards):
            rotate = ind == len(hand.cards) - 1 and rotate_last is True
            img, width, height = self.components.get_image(card, rotate=rotate)
            self.components.slot_player[
                f"{str(hand.slot)}{str(ind)}"
            ].configure(image=img, width=width, height=height)
            self.components.slot_player[
                f"{str(hand.slot)}{str(ind)}"
            ].image = img  # type: ignore
        
        self.root.update()
        self.delayed_ui()

    def display_player_cards_rotate(self, hand: Hand):
        two_aces = hand.cards[0].label == "A" and hand.cards[1].label == "A"
        rotate = hand.cards[0].label == "A" and hand.cards[1].label != "A"
        if two_aces and not self.rules.resplit_aces:
            rotate = True
        self.display_player_cards(hand, rotate_last=rotate)
        self.root.update()

    ##########
    ## Shoe ##
    ##########

    # Used to display amount of cards in shoe in relation to the initial state
    def fill_discard_tray(self, shoe: Shoe) -> None:
        """[UI] Updates shoe displayed state"""
        fraction = (shoe._n_cards_total - shoe.n_cards) / shoe._n_cards_total
        y = shoe.n_decs * 20
        if self.components.shoe_progress is not None:
            self.components.shoe_progress.place(
                x=30, y=y, anchor="se", relheight=fraction, relwidth=1.0
            )
        self.root.update()

    def animate_shuffle(self, shoe: Shoe):
        self.fill_discard_tray(shoe)
        self._show_shuffle()
        self.delayed_ui(TIME_DELAY*2)
        self._finish_shuffle()
        self.root.update()

    def _show_shuffle(self):
        self.components.shuffle.place(relx=0.45, rely=0.5, anchor="center")
        self.root.update_idletasks()

    def _finish_shuffle(self):
        self._hide_shuffle()
        self.root.update()
    
    def _hide_shuffle(self):
        self.components.shuffle.place_forget()
        self.root.update()


    ###########
    ## Chips ##
    ###########
    
    def display_chips(self, hand: Hand, bet, bj: bool = False, triple: bool = False):
        """[UI]"""
        if bj is True:
            self.display_chip(hand, 1, bet)
            self.display_chip(hand, 4, bet, color="blue")
        elif triple is True:
            self.display_chip(hand, 0, bet)
            self.display_chip(hand, 1, bet)
            self.display_chip(hand, 2, bet)
        elif hand.bet == bet:
            self.display_chip(hand, 1, bet)
        elif hand.bet == (2 * bet):
            self.display_chip(hand, 2, bet)
            self.display_chip(hand, 3, bet)

        self.root.update()


    def display_insurance_chip(self, insurance_bet, triple: bool = False):
        """[UI]"""
        bet = (
            insurance_bet
            if triple is False
            else insurance_bet * 3
        )
        color = "red"
        if bet == 0.5:
            color = "blue"
            text = "0.5"
        elif bet % 1 == 0:
            text = str(round(bet))
        else:
            text = str(bet)
        img = self._get_chip_image(color)
        self.components.insurance_chip.configure(
            image=img,
            compound="center",
            fg="white",
            text=text,
            font="helvetica 10 bold",
        )
        self.components.insurance_chip.image = img  # type: ignore
        self.root.update()

    def hide_insurance_chip(self):
        """[UI]"""
        self.components.insurance_chip.configure(image="", text="")
        self.root.update()


    def display_chip(self, hand: Hand, pos: int, bet, color: str = "red"):
        """[UI]"""
        img = self._get_chip_image(color)
        if color == "red":
            text = str(bet)
        else:
            text = "0.5" if bet == 1 else str(bet / 2)
        self.components.chips[f"{str(hand.slot)}{str(pos)}"].configure(
            image=img,
            compound="center",
            fg="white",
            text=text,
            font="helvetica 10 bold",
        )
        self.components.chips[f"{str(hand.slot)}{str(pos)}"].image = img  # type: ignore
        self.root.update()

    def hide_all_chips(self):
        """[UI]"""
        for chip in self.components.chips.values():
            chip.configure(image="", text="")

        self.root.update()

    def hide_chips(self, hand: Hand):
        """[UI]"""
        for pos in range(4):
            self.components.chips[f"{str(hand.slot)}{str(pos)}"].configure(
                image="", text=""
            )
        self.root.update()

    def _get_chip_image(self, color: str = "red") -> ImageTk.PhotoImage:
        size = 50
        filename = f"{self.img_path}/{color}-chip.png"
        image = Image.open(filename).resize(
            (size, size - 15), Image.Resampling.LANCZOS
        )
        return ImageTk.PhotoImage(image)




    ###########
    ## Stack ##
    ###########

    def display_stack(self, stack):
        """[UI]"""
        unit = "$" if self.rules.region == "US" else "€"
        self.components.label_text.set(f"Stack: {stack} {unit}")
        self.root.update()

    ############
    ### Info ###
    ############

    def display_info(self, hand: Hand, info: str):
        """[UI]"""
        self.components.info_text[str(hand.slot)].set(info)
        self.root.update()
        self.delayed_ui()

    def clean_info(self):
        """[UI]"""
        for slot in range(4):
            self.components.info_text[str(slot)].set("")
            self.root.update()

    def dealer_info(self, text: str = ""):
        """[UI]"""
        self.components.dealer_info.configure(text=text)
        self.root.update()

    ############

    def delayed_ui(self, time_delay=TIME_DELAY):
        """[UI]"""
        time.sleep(time_delay)

    def display_finger(self, hand: Hand):
        """[UI]"""
        self.hide_fingers()
        img = self._get_finger_image()
        self.components.finger[f"{str(hand.slot)}"].configure(image=img)
        self.components.finger[f"{str(hand.slot)}"].image = img  # type: ignore
        self.root.update()

    def hide_fingers(self):
        """[UI]"""
        for finger in self.components.finger.values():
            finger.configure(image="")
        
        self.root.update()


    def _get_finger_image(self) -> ImageTk.PhotoImage:
        filename = f"{self.img_path}/finger2.png"
        image = Image.open(filename).resize((40, 60), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)
    