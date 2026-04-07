import tkinter
import time
from .settings import set_window_position
from ..lib import Shoe, Hand, Card
from table_components import TableComponents
from PIL import Image, ImageTk

class GameUI:
    def __init__(
        self,
        args,
        n_cards_max,
        img_path,
        background,
    ):
        self.root = tkinter.Tk()
        set_window_position(self.root, 1200, 700)
        self.background = background
        self.n_cards_max = n_cards_max
        self.components = self.start_components(args)
        self.args = args
        self.rules = args.rules
        self.img_path = img_path
        self.set_description()

    def start_components(self, args):
        components = TableComponents(self.root, self.background)
        components.setup_canvas()
        components.get_shoe_progress(args.rules.number_of_decks)
        components.get_label()
        components.get_dealer_info()
        components.get_info()
        components.get_finger()
        components.get_player_slots(self.n_cards_max)
        components.get_chips()
        components.get_dealer_slot()
        components.get_insurance_chip()
        components.get_shuffle_indicator()
        components.set_side_panel()
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
        self.hide_all_chips()
        self.hide_insurance_chip()
        self.hide_fingers()
        self._clean_player_slots()
        self.dealer_info()

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

    def hide(self, hand: Hand):
        """[UI]"""
        for n in range(self.n_cards_max):
            self.components.slot_player[f"{str(hand.slot)}{str(n)}"].configure(
                state=tkinter.DISABLED
            )

    def _clean_player_slots(self):
        """[UI]"""
        for slot in range(4):
            for n in range(self.n_cards_max):
                self.components.slot_player[f"{str(slot)}{str(n)}"].configure(
                    image="", width=0, height=0
                )

    def clean_dealer_slots(self):
        """[UI]"""
        for pos in self.components.slot_dealer.values():
            pos.configure(image="", width=0)



    def display_dealer_cards(self, hide_second: bool = True):
        """[UI]"""
        for ind, card in enumerate(self.dealer.cards):
            if ind == 1 and hide_second is True and len(self.dealer.cards) == 2:
                img, width, _ = self._get_image()
            else:
                img, width, _ = self._get_image(card)
            self.components.slot_dealer[str(ind)].configure(
                image=img, width=width
            )
            self.components.slot_dealer[str(ind)].image = img  # type: ignore

    def display_player_cards(self, hand: Hand, rotate_last: bool = False):
        """[UI]"""
        for ind, card in enumerate(hand.cards):
            rotate = ind == len(hand.cards) - 1 and rotate_last is True
            img, width, height = self._get_image(card, rotate=rotate)
            self.components.slot_player[
                f"{str(hand.slot)}{str(ind)}"
            ].configure(image=img, width=width, height=height)
            self.components.slot_player[
                f"{str(hand.slot)}{str(ind)}"
            ].image = img  # type: ignore

    def display_player_cards_rotate(self, hand: Hand):
        two_aces = hand.cards[0].label == "A" and hand.cards[1].label == "A"
        rotate = hand.cards[0].label == "A" and hand.cards[1].label != "A"
        if two_aces and not self.rules.resplit_aces:
            rotate = True
        self.display_player_cards(hand, rotate_last=rotate)

    ##########
    ## Shoe ##
    ##########

    # Used to display amount of cards in shoe in relation to the initial state
    def fill_discard_tray(self, shoe) -> None:
        """[UI] Updates shoe displayed state"""
        fraction = (shoe._n_cards_total - shoe.n_cards) / shoe._n_cards_total
        y = shoe.n_decs * 20
        if self.components.shoe_progress is not None:
            self.components.shoe_progress.place(
                x=30, y=y, anchor="se", relheight=fraction, relwidth=1.0
            )

    def animate_shuffle(self, shoe: Shoe, time_delay):
        self.fill_discard_tray(shoe)
        self._show_shuffle()
        self.delayed_ui(time_delay*2)
        self._finish_shuffle()

    def _show_shuffle(self):
        self.components.shuffle.place(relx=0.45, rely=0.5, anchor="center")
        self.root.update_idletasks()

    def _finish_shuffle(self):
        self._hide_shuffle()
    
    def _hide_shuffle(self):
        self.components.shuffle.place_forget()


    ###########
    ## Chips ##
    ###########
    
    def display_chips(self, hand, bj: bool = False, triple: bool = False):
        """[UI]"""
        if bj is True:
            self._display_chip(hand, 1)
            self._display_chip(hand, 4, color="blue")
        elif triple is True:
            self._display_chip(hand, 0)
            self._display_chip(hand, 1)
            self._display_chip(hand, 2)
        elif hand.bet == self.bet:
            self._display_chip(hand, 1)
        elif hand.bet == (2 * self.bet):
            self._display_chip(hand, 2)
            self._display_chip(hand, 3)

    def display_insurance_chip(self, triple: bool = False):
        """[UI]"""
        bet = (
            self.dealer.insurance_bet
            if triple is False
            else self.dealer.insurance_bet * 3
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


    def hide_insurance_chip(self):
        """[UI]"""
        self.components.insurance_chip.configure(image="", text="")


    def display_chip(self, hand: Hand, pos: int, color: str = "red"):
        """[UI]"""
        img = self._get_chip_image(color)
        if color == "red":
            text = str(self.bet)
        else:
            text = "0.5" if self.bet == 1 else str(self.bet / 2)
        self.components.chips[f"{str(hand.slot)}{str(pos)}"].configure(
            image=img,
            compound="center",
            fg="white",
            text=text,
            font="helvetica 10 bold",
        )
        self.components.chips[f"{str(hand.slot)}{str(pos)}"].image = img  # type: ignore

    def hide_all_chips(self):
        """[UI]"""
        for chip in self.components.chips.values():
            chip.configure(image="", text="")

    def hide_chips(self, hand: Hand):
        """[UI]"""
        for pos in range(4):
            self.components.chips[f"{str(hand.slot)}{str(pos)}"].configure(
                image="", text=""
            )

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

    def _display_stack(self, stack):
        """[UI]"""
        unit = "$" if self.rules.region == "US" else "€"
        self.components.label_text.set(f"Stack: {stack} {unit}")

    ############
    ### Info ###
    ############

    def display_info(self, hand: Hand, info: str):
        """[UI]"""
        self.components.info_text[str(hand.slot)].set(info)

    def clean_info(self):
        """[UI]"""
        for slot in range(4):
            self.components.info_text[str(slot)].set("")

    def dealer_info(self, text: str = ""):
        """[UI]"""
        self.components.dealer_info.configure(text=text)

    ############

    def delayed_ui(self, time_delay):
        """[UI]"""
        time.sleep(time_delay)

    def display_finger(self, hand: Hand):
        """[UI]"""
        self._hide_fingers()
        img = self._get_finger_image()
        self.components.finger[f"{str(hand.slot)}"].configure(image=img)
        self.components.finger[f"{str(hand.slot)}"].image = img  # type: ignore

    def hide_fingers(self):
        """[UI]"""
        for finger in self.components.finger.values():
            finger.configure(image="")


    def _get_finger_image(self) -> ImageTk.PhotoImage:
        filename = f"{self.img_path}/finger2.png"
        image = Image.open(filename).resize((40, 60), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)
    

    def _get_image(
        self,
        card: Card | None = None,
        width: int = 100,
        height: int = 130,
        rotate: bool = False,
    ):
        if card is None:
            filename = f"{self.img_path}/back.png"
        else:
            mapping = {
                "A": "ace",
                "J": "jack",
                "Q": "queen",
                "K": "king",
            }
            prefix = mapping.get(card.label, card.value)
            filename = f"{self.img_path}/{prefix}_of_{card.suit}.png"
        image = Image.open(filename).resize(
            (width, height), Image.Resampling.LANCZOS
        )
        if rotate is True:
            image = image.resize((height, height))
            image = image.rotate(angle=90)
            image = image.resize((height, width))
            width, height = height, width
        return ImageTk.PhotoImage(image), width, height

