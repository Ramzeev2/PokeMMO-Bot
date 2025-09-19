import tkinter as tk
import threading
import time
import cv2
import numpy as np
from PIL import ImageGrab
import os
from dataclasses import dataclass
from enum import Enum
import pydirectinput

# Configure pydirectinput
pydirectinput.PAUSE = 0.01

class BotState(Enum):
    """Bot states for clear state management"""
    STOPPED = "stopped"
    MOVING = "moving"
    IN_BATTLE = "in_battle"
    ATTACKING = "attacking"
    RUNNING = "running"
    TELEPORTING = "teleporting"
    HEALING = "healing"

class Direction(Enum):
    """Character movement directions"""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

@dataclass
class BotConfig:
    """Configuration settings for the bot"""
    # Movement timings
    time_per_space: float = 0.20  # Time to move one tile when facing correct direction
    time_to_turn: float = 0.12    # Time to turn character to face new direction
    movement_delay: float = 0.5    # Delay between movement cycles
    
    # Battle settings
    detection_threshold: float = 0.8
    attack_wait_time: float = 11.0
    startup_delay: int = 3
    selected_ability: int = 1  # Which ability to use (1-4)
    backup_ability: int = 2    # Backup ability when main runs out of PP
    use_backup: bool = True    # Whether to use backup ability
    
    # Abra Teleport settings
    use_abra_teleport: bool = False  # Whether to teleport when out of PP
    
    # PP tracking
    max_pp: dict = None  # Max PP for each ability
    current_pp: dict = None  # Current PP for each ability
    
    def __post_init__(self):
        if self.max_pp is None:
            self.max_pp = {1: 20, 2: 20, 3: 20, 4: 20}
        if self.current_pp is None:
            self.current_pp = self.max_pp.copy()

class ImageDetector:
    """Handles all image detection operations"""
    
    def __init__(self):
        self.templates = {}
        self.load_templates()
    
    def load_templates(self):
        """Load all template images"""
        template_files = {
            'hp_bar': ['hp_bar.png', 'hp_bar.jpg'],
            'battle_menu': ['battle_menu.png', 'battle_options.png', 'battle_menu.jpg']
        }
        
        for name, files in template_files.items():
            for file in files:
                if os.path.exists(file):
                    template = cv2.imread(file)
                    if template is not None:
                        self.templates[name] = template
                        break
    
    def load_template(self, name, filepath):
        """Load a specific template"""
        template = cv2.imread(filepath)
        if template is not None:
            self.templates[name] = template
            return True
        return False
    
    def detect(self, template_name, threshold=0.8):
        """Detect if a template is present on screen"""
        if template_name not in self.templates:
            return False
        
        try:
            screenshot = ImageGrab.grab()
            screenshot_np = np.array(screenshot)
            screenshot_bgr = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            
            result = cv2.matchTemplate(
                screenshot_bgr, 
                self.templates[template_name], 
                cv2.TM_CCOEFF_NORMED
            )
            
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            return max_val >= threshold
            
        except Exception as e:
            print(f"Detection error for {template_name}: {e}")
            return False
    
    def is_in_battle(self, threshold=0.8):
        """Check if currently in battle by detecting HP bar"""
        return self.detect('hp_bar', threshold)
    
    def is_battle_menu_visible(self, threshold=0.8):
        """Check if battle menu (FIGHT, BAG, etc.) is visible"""
        return self.detect('battle_menu', threshold)

class BattleController:
    """Handles all battle-related actions"""
    
    def __init__(self, detector, config):
        self.detector = detector
        self.config = config
    
    def get_ability_to_use(self):
        """Determine which ability to use based on PP"""
        # Check if main ability has PP
        if self.config.current_pp[self.config.selected_ability] > 0:
            return self.config.selected_ability
        
        # Check if we should use backup
        if self.config.use_backup and self.config.current_pp[self.config.backup_ability] > 0:
            return self.config.backup_ability
        
        # No PP left on selected abilities - run from battle
        return None
    
    def select_fight_and_ability(self, ability=None):
        """Select FIGHT option and use the selected ability"""
        if ability is None:
            ability = self.get_ability_to_use()
        
        if ability is None:
            # No PP left, run instead
            return False
        
        # First, select FIGHT option (up + z)
        pydirectinput.press('up')
        time.sleep(0.1)
        pydirectinput.press('z')
        time.sleep(0.3)
        
        # Navigate to abilities menu
        pydirectinput.press('up')
        time.sleep(0.1)
        
        # Reset position to top-left (ability 1) by pressing up and left
        pydirectinput.press('up')
        time.sleep(0.1)
        pydirectinput.press('left')
        time.sleep(0.1)
        
        # Now navigate to the appropriate ability
        if ability == 1:
            # First ability - we're already there, just press z
            pydirectinput.press('z')
            
        elif ability == 2:
            # Second ability - right then z
            pydirectinput.press('right')
            time.sleep(0.1)
            pydirectinput.press('z')
            
        elif ability == 3:
            # Third ability - down then z
            pydirectinput.press('down')
            time.sleep(0.1)
            pydirectinput.press('z')
            
        elif ability == 4:
            # Fourth ability - down, right then z
            pydirectinput.press('down')
            time.sleep(0.1)
            pydirectinput.press('right')
            time.sleep(0.1)
            pydirectinput.press('z')
        
        # Deduct PP
        self.config.current_pp[ability] -= 1
        time.sleep(0.3)
        return True
    
    def select_run(self):
        """Select RUN option to flee from battle"""
        # Select RUN option (up, down, right + z)
        pydirectinput.press('up')
        time.sleep(0.1)
        pydirectinput.press('down')
        time.sleep(0.1)
        pydirectinput.press('right')
        time.sleep(0.1)
        pydirectinput.press('z')
        time.sleep(0.3)
        
        # Return True to indicate we're running
        return True
    
    def handle_battle(self):
        """Complete battle handling logic"""
        while self.detector.is_in_battle(self.config.detection_threshold):
            if self.detector.is_battle_menu_visible(self.config.detection_threshold):
                # Try to fight, run if no PP
                if not self.select_fight_and_ability():
                    # We're running from battle
                    if self.select_run():
                        # Increment run counter here when we actually run
                        return "run"
            
            time.sleep(self.config.attack_wait_time)
            
            if not self.detector.is_in_battle(self.config.detection_threshold):
                break
        
        return "battle_complete"

class SmartMovementController:
    """Smart movement controller using background input with precise timing"""
    
    def __init__(self, config, pattern="horizontal"):
        self.config = config
        self.pattern = pattern
        self.current_direction = Direction.LEFT if pattern == "horizontal" else Direction.UP
        self.spaces_to_move = 1  # Default to moving 1 space each direction
        
        # Movement keys mapping
        self.direction_keys = {
            Direction.LEFT: 'left',
            Direction.RIGHT: 'right',
            Direction.UP: 'up',
            Direction.DOWN: 'down'
        }
    
    def move(self, direction: Direction, spaces: int = 1):
        """Move in specified direction for specified number of spaces"""
        key = self.direction_keys[direction]
        
        # Calculate time needed
        turn_time = 0
        if self.current_direction != direction:
            turn_time = self.config.time_to_turn
            self.current_direction = direction
        
        # Total time = turn time + (time per space * number of spaces)
        total_time = turn_time + (self.config.time_per_space * spaces)
        
        # Execute movement
        pydirectinput.keyDown(key)
        time.sleep(total_time)
        pydirectinput.keyUp(key)
        
        # Small delay after movement
        time.sleep(0.1)
    
    def move_cycle(self):
        """Execute one movement cycle based on pattern"""
        if self.pattern == "horizontal":
            # Move left then right
            self.move(Direction.LEFT, self.spaces_to_move)
            time.sleep(0.2)  # Small pause at edge
            self.move(Direction.RIGHT, self.spaces_to_move)
            time.sleep(0.2)  # Small pause at edge
            
        elif self.pattern == "vertical":
            # Move up then down
            self.move(Direction.UP, self.spaces_to_move)
            time.sleep(0.2)
            self.move(Direction.DOWN, self.spaces_to_move)
            time.sleep(0.2)
    
    def set_pattern(self, pattern):
        """Update movement pattern"""
        self.pattern = pattern
        if pattern == "horizontal":
            self.current_direction = Direction.LEFT
        else:
            self.current_direction = Direction.UP
    
    def set_spaces(self, spaces):
        """Set number of spaces to move in each direction"""
        self.spaces_to_move = spaces

class PokemonBot:
    """Main bot controller"""
    
    def __init__(self):
        self.state = BotState.STOPPED
        self.config = BotConfig()
        self.detector = ImageDetector()
        self.battle_controller = BattleController(self.detector, self.config)
        self.movement_controller = SmartMovementController(self.config)
        self.stats = {"movements": 0, "battles": 0, "runs": 0}
        self.running = False
    
    def start(self):
        """Start the bot"""
        self.running = True
        self.state = BotState.MOVING
        threading.Thread(target=self.main_loop, daemon=True).start()
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        self.state = BotState.STOPPED
    
    def teleport_to_pokecenter(self):
        """Teleport to the nearest Pokémon Center using Abra (key 9)"""
        # Make sure we're not in battle
        if not self.detector.is_in_battle(self.config.detection_threshold):
            self.state = BotState.TELEPORTING
            print("Teleporting to Pokémon Center...")
            pydirectinput.press('9')
            time.sleep(6)  # Wait for teleport animation
            return True
        return False
    
    def heal_pokemon_at_center(self):
        """Interact 5 times to heal Pokémon at the center"""
        self.state = BotState.HEALING
        print("Healing Pokémon at center...")
        
        # Interact 5 times with nurse
        time.sleep(0.8)
        pydirectinput.press('z')
        time.sleep(0.8)
        pydirectinput.press('z')        
        time.sleep(0.8)
        pydirectinput.press('z')       
        time.sleep(0.8)
        pydirectinput.press('z')
        time.sleep(0.8)
        pydirectinput.press('z') 
        time.sleep(0.8)
 
        # Reset PP after healing
        for ability in range(1, 5):
            self.config.current_pp[ability] = self.config.max_pp[ability]
        
        print("Pokémon healed! Stopping bot...")
        # Stop the bot after healing
        self.stop()
    
    def main_loop(self):
        """Main bot logic loop"""
        time.sleep(self.config.startup_delay)
        
        while self.running:
            if self.detector.is_in_battle(self.config.detection_threshold):
                self.state = BotState.IN_BATTLE
                self.stats["battles"] += 1
                
                # Check if we have any PP left
                has_pp = any(pp > 0 for pp in self.config.current_pp.values())
                if not has_pp:
                    self.state = BotState.RUNNING
                else:
                    self.state = BotState.ATTACKING
                
                # Handle the battle and check the result
                result = self.battle_controller.handle_battle()
                if result == "run":
                    self.state = BotState.RUNNING
                    self.stats["runs"] += 1
                    
                    # Check if we should use Abra Teleport
                    if self.config.use_abra_teleport:
                        time.sleep(2)  # Wait for run animation to complete
                        if self.teleport_to_pokecenter():
                            time.sleep(2)  # Wait after teleport
                            self.heal_pokemon_at_center()
                            # Bot will stop after healing
                            return
                
                self.state = BotState.MOVING
            
            elif self.state == BotState.MOVING:
                self.movement_controller.move_cycle()
                self.stats["movements"] += 1
                time.sleep(self.config.movement_delay)
            
            time.sleep(0.1)

class BotGUI:
    """GUI for the Pokemon Bot"""
    
    def __init__(self):
        self.bot = PokemonBot()
        self.pp_entries = {}
        self.setup_gui()
    
    def setup_gui(self):
        """Create the GUI"""
        self.window = tk.Tk()
        self.window.title("Pokemon Smart Bot - PP Tracking Edition")
        self.window.geometry("450x1150")  # Increased for Abra Teleport section
        self.window.resizable(False, False)
        
        # Title
        tk.Label(self.window, text="Pokemon Smart Movement Bot", 
                font=("Arial", 16, "bold")).pack(pady=10)
        
        # Status
        self.status_label = tk.Label(self.window, text="Status: Stopped", 
                                     fg="red", font=("Arial", 12))
        self.status_label.pack(pady=5)
        
        # Template status
        self.create_template_section()
        
        # Battle settings (including ability selection and PP)
        self.create_battle_section()
        
        # Movement settings
        self.create_movement_section()
        
        # Timing settings
        self.create_timing_section()
        
        # Statistics
        self.create_stats_section()
        
        # Control button
        self.control_button = tk.Button(self.window, text="START BOT",
                                       command=self.toggle_bot,
                                       bg="#4CAF50", fg="white",
                                       font=("Arial", 14, "bold"),
                                       width=15, height=2)
        self.control_button.pack(pady=20)
        
        # Update loop
        self.update_display()
        
        self.window.mainloop()
    
    
    def create_template_section(self):
        """Create template loading section"""
        template_frame = tk.LabelFrame(self.window, text="Templates", padx=10, pady=5)
        template_frame.pack(pady=5, padx=10, fill="x")
        
        # Status labels
        status_frame = tk.Frame(template_frame)
        status_frame.pack(pady=2)
        
        hp_status = "✓" if 'hp_bar' in self.bot.detector.templates else "✗"
        self.hp_label = tk.Label(status_frame, 
                                 text=f"HP Bar: {hp_status}",
                                 fg="green" if hp_status == "✓" else "red")
        self.hp_label.pack(side=tk.LEFT, padx=5)
        
        menu_status = "✓" if 'battle_menu' in self.bot.detector.templates else "✗"
        self.menu_label = tk.Label(status_frame, 
                                   text=f"Battle Menu: {menu_status}",
                                   fg="green" if menu_status == "✓" else "red")
        self.menu_label.pack(side=tk.LEFT, padx=5)
        
        # Load buttons
        button_frame = tk.Frame(template_frame)
        button_frame.pack(pady=5)
        
        tk.Button(button_frame, text="Load HP Bar",
                 command=lambda: self.load_template('hp_bar')).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Load Battle Menu",
                 command=lambda: self.load_template('battle_menu')).pack(side=tk.LEFT, padx=5)
    
    def create_battle_section(self):
        """Create battle settings section including ability selection and PP tracking"""
        battle_frame = tk.LabelFrame(self.window, text="Battle Settings", padx=10, pady=5)
        battle_frame.pack(pady=5, padx=10, fill="x")
        
        # Main ability selection
        main_frame = tk.Frame(battle_frame)
        main_frame.pack(pady=5)
        
        tk.Label(main_frame, text="Main Ability:", font=("Arial", 10, "bold")).pack()
        
        # Radio buttons for main ability selection
        self.ability_var = tk.IntVar(value=1)
        
        abilities_row = tk.Frame(main_frame)
        abilities_row.pack()
        
        for i in range(1, 5):
            tk.Radiobutton(abilities_row, text=f"Ability {i}",
                          variable=self.ability_var, value=i,
                          command=self.update_ability).pack(side=tk.LEFT, padx=5)
        
        # Backup ability section
        backup_frame = tk.Frame(battle_frame)
        backup_frame.pack(pady=5)
        
        # Use backup checkbox
        self.use_backup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(backup_frame, text="Use Backup Ability",
                      variable=self.use_backup_var,
                      command=self.update_backup_usage).pack()
        
        # Backup ability selection
        tk.Label(backup_frame, text="Backup Ability:", font=("Arial", 9)).pack()
        self.backup_var = tk.IntVar(value=2)
        
        backup_row = tk.Frame(backup_frame)
        backup_row.pack()
        
        for i in range(1, 5):
            tk.Radiobutton(backup_row, text=f"{i}",
                          variable=self.backup_var, value=i,
                          command=self.update_backup).pack(side=tk.LEFT, padx=5)
        
        # PP Settings
        pp_frame = tk.LabelFrame(battle_frame, text="PP Management", padx=5, pady=5)
        pp_frame.pack(pady=10, fill="x")
        
        # Max PP entries
        tk.Label(pp_frame, text="Max PP for each ability:", font=("Arial", 9)).pack()
        
        pp_input_frame = tk.Frame(pp_frame)
        pp_input_frame.pack(pady=5)
        
        for i in range(1, 5):
            col_frame = tk.Frame(pp_input_frame)
            col_frame.pack(side=tk.LEFT, padx=5)
            tk.Label(col_frame, text=f"Ability {i}:", font=("Arial", 8)).pack()
            
            entry = tk.Entry(col_frame, width=8)
            entry.insert(0, "20")
            entry.pack()
            self.pp_entries[i] = entry
            
            # Bind to update PP when changed
            entry.bind('<FocusOut>', lambda e, ability=i: self.update_pp(ability))
            entry.bind('<Return>', lambda e, ability=i: self.update_pp(ability))
        
        # Current PP display
        self.pp_display_frame = tk.Frame(pp_frame)
        self.pp_display_frame.pack(pady=5)
        
        self.pp_labels = {}
        for i in range(1, 5):
            label = tk.Label(self.pp_display_frame, 
                           text=f"PP {i}: 20/20",
                           font=("Arial", 8))
            label.pack(side=tk.LEFT, padx=5)
            self.pp_labels[i] = label
        
        # Reset PP button
        tk.Button(pp_frame, text="Reset All PP",
                 command=self.reset_pp,
                 bg="#2196F3", fg="white").pack(pady=5)
        
        # Abra Teleport checkbox
        teleport_frame = tk.Frame(battle_frame)
        teleport_frame.pack(pady=5)
        
        self.abra_teleport_var = tk.BooleanVar(value=False)
        tk.Checkbutton(teleport_frame, text="Abra Teleport (Press 9 when out of PP)",
                      variable=self.abra_teleport_var,
                      command=self.update_abra_teleport,
                      font=("Arial", 9, "bold"),
                      fg="purple").pack()
        
        tk.Label(teleport_frame, 
                text="Auto-teleports to PokéCenter, heals, and stops bot",
                font=("Arial", 8),
                fg="gray").pack()
        
        # Visual indicator for selected abilities
        self.ability_label = tk.Label(battle_frame, 
                                     text="Using: Main Ability 1, Backup Ability 2",
                                     fg="blue", font=("Arial", 9))
        self.ability_label.pack(pady=2)
    
    def create_movement_section(self):
        """Create movement settings section"""
        movement_frame = tk.LabelFrame(self.window, text="Movement Settings", padx=10, pady=5)
        movement_frame.pack(pady=5, padx=10, fill="x")
        
        # Pattern selection
        pattern_frame = tk.Frame(movement_frame)
        pattern_frame.pack(pady=5)
        
        tk.Label(pattern_frame, text="Pattern:").pack(side=tk.LEFT)
        self.pattern_var = tk.StringVar(value="horizontal")
        tk.Radiobutton(pattern_frame, text="Left ↔ Right",
                      variable=self.pattern_var, value="horizontal",
                      command=self.update_pattern).pack(side=tk.LEFT)
        tk.Radiobutton(pattern_frame, text="Up ↕ Down",
                      variable=self.pattern_var, value="vertical",
                      command=self.update_pattern).pack(side=tk.LEFT)
        
        # Spaces to move
        spaces_frame = tk.Frame(movement_frame)
        spaces_frame.pack(pady=5)
        
        tk.Label(spaces_frame, text="Spaces to move:").pack(side=tk.LEFT)
        self.spaces_scale = tk.Scale(spaces_frame, from_=1, to=4,
                                    orient=tk.HORIZONTAL,
                                    command=self.update_spaces)
        self.spaces_scale.set(1)
        self.spaces_scale.pack(side=tk.LEFT)
    
    def create_timing_section(self):
        """Create timing adjustment section"""
        timing_frame = tk.LabelFrame(self.window, text="Timing Settings", padx=10, pady=5)
        timing_frame.pack(pady=5, padx=10, fill="x")
        
        # Time per space
        space_frame = tk.Frame(timing_frame)
        space_frame.pack(pady=2)
        tk.Label(space_frame, text="Time per space:").pack(side=tk.LEFT)
        self.space_time_scale = tk.Scale(space_frame, from_=0.15, to=0.30,
                                        orient=tk.HORIZONTAL, resolution=0.01,
                                        command=self.update_space_time)
        self.space_time_scale.set(0.20)
        self.space_time_scale.pack(side=tk.LEFT)
        
        # Turn time
        turn_frame = tk.Frame(timing_frame)
        turn_frame.pack(pady=2)
        tk.Label(turn_frame, text="Turn time:").pack(side=tk.LEFT)
        self.turn_time_scale = tk.Scale(turn_frame, from_=0.08, to=0.20,
                                       orient=tk.HORIZONTAL, resolution=0.01,
                                       command=self.update_turn_time)
        self.turn_time_scale.set(0.12)
        self.turn_time_scale.pack(side=tk.LEFT)
        
        # Movement delay
        delay_frame = tk.Frame(timing_frame)
        delay_frame.pack(pady=2)
        tk.Label(delay_frame, text="Cycle delay:").pack(side=tk.LEFT)
        self.delay_scale = tk.Scale(delay_frame, from_=0.3, to=2.0,
                                   orient=tk.HORIZONTAL, resolution=0.1,
                                   command=self.update_delay)
        self.delay_scale.set(0.5)
        self.delay_scale.pack(side=tk.LEFT)
    
    def create_stats_section(self):
        """Create statistics section"""
        stats_frame = tk.LabelFrame(self.window, text="Statistics", padx=10, pady=5)
        stats_frame.pack(pady=5, padx=10, fill="x")
        
        self.moves_label = tk.Label(stats_frame, text="Movement Cycles: 0")
        self.moves_label.pack(anchor=tk.W)
        
        self.battles_label = tk.Label(stats_frame, text="Battles: 0")
        self.battles_label.pack(anchor=tk.W)
        
        self.runs_label = tk.Label(stats_frame, text="Runs from Battle: 0")
        self.runs_label.pack(anchor=tk.W)
    
    def load_template(self, template_type):
        """Load a template image"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            title=f"Select {template_type.replace('_', ' ').title()} Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")]
        )
        
        if filename:
            if self.bot.detector.load_template(template_type, filename):
                ext = os.path.splitext(filename)[1]
                cv2.imwrite(f"{template_type}{ext}", cv2.imread(filename))
                self.update_template_status()
    
    def update_template_status(self):
        """Update template status labels"""
        hp_status = "✓" if 'hp_bar' in self.bot.detector.templates else "✗"
        self.hp_label.config(text=f"HP Bar: {hp_status}",
                            fg="green" if hp_status == "✓" else "red")
        
        menu_status = "✓" if 'battle_menu' in self.bot.detector.templates else "✗"
        self.menu_label.config(text=f"Battle Menu: {menu_status}",
                              fg="green" if menu_status == "✓" else "red")
    
    def update_abra_teleport(self):
        """Update Abra Teleport setting"""
        self.bot.config.use_abra_teleport = self.abra_teleport_var.get()
    
    def update_ability(self):
        """Update selected ability"""
        ability = self.ability_var.get()
        self.bot.config.selected_ability = ability
        self.update_ability_label()
    
    def update_backup(self):
        """Update backup ability"""
        backup = self.backup_var.get()
        self.bot.config.backup_ability = backup
        self.update_ability_label()
    
    def update_backup_usage(self):
        """Update whether to use backup"""
        self.bot.config.use_backup = self.use_backup_var.get()
        self.update_ability_label()
    
    def update_ability_label(self):
        """Update the ability status label"""
        main = self.bot.config.selected_ability
        backup = self.bot.config.backup_ability
        use_backup = self.bot.config.use_backup
        
        if use_backup:
            text = f"Using: Main Ability {main}, Backup Ability {backup}"
        else:
            text = f"Using: Main Ability {main} (No Backup)"
        
        self.ability_label.config(text=text)
    
    def update_pp(self, ability):
        """Update PP for an ability"""
        try:
            value = int(self.pp_entries[ability].get())
            if value > 0:
                self.bot.config.max_pp[ability] = value
                self.bot.config.current_pp[ability] = value
                self.update_pp_display()
        except ValueError:
            self.pp_entries[ability].delete(0, tk.END)
            self.pp_entries[ability].insert(0, str(self.bot.config.max_pp[ability]))
    
    def reset_pp(self):
        """Reset all PP to maximum"""
        for ability in range(1, 5):
            self.bot.config.current_pp[ability] = self.bot.config.max_pp[ability]
        self.update_pp_display()
    
    def update_pp_display(self):
        """Update PP display labels"""
        for ability in range(1, 5):
            current = self.bot.config.current_pp[ability]
            maximum = self.bot.config.max_pp[ability]
            self.pp_labels[ability].config(
                text=f"PP {ability}: {current}/{maximum}",
                fg="green" if current > 0 else "red"
            )
    
    def update_pattern(self):
        """Update movement pattern"""
        self.bot.movement_controller.set_pattern(self.pattern_var.get())
    
    def update_spaces(self, value):
        """Update number of spaces to move"""
        self.bot.movement_controller.set_spaces(int(value))
    
    def update_space_time(self, value):
        """Update time per space"""
        self.bot.config.time_per_space = float(value)
    
    def update_turn_time(self, value):
        """Update turn time"""
        self.bot.config.time_to_turn = float(value)
    
    def update_delay(self, value):
        """Update movement delay"""
        self.bot.config.movement_delay = float(value)
    
    def toggle_bot(self):
        """Start or stop the bot"""
        if not self.bot.running:
            if 'hp_bar' not in self.bot.detector.templates:
                self.status_label.config(text="Load HP Bar image first!", fg="red")
                return
            
            # Update all PP values before starting
            for ability in range(1, 5):
                self.update_pp(ability)
            
            self.bot.start()
            self.control_button.config(text="STOP BOT", bg="#f44336")
            self.status_label.config(text="Status: Running", fg="green")
        else:
            self.bot.stop()
            self.control_button.config(text="START BOT", bg="#4CAF50")
            self.status_label.config(text="Status: Stopped", fg="red")
    
    def update_display(self):
        """Update GUI display"""
        if self.bot.running:
            status_text = f"Status: {self.bot.state.value.title()}"
            self.status_label.config(text=status_text)
            
            self.moves_label.config(text=f"Movement Cycles: {self.bot.stats['movements']}")
            self.battles_label.config(text=f"Battles: {self.bot.stats['battles']}")
            self.runs_label.config(text=f"Runs from Battle: {self.bot.stats.get('runs', 0)}")
            
            # Update PP display
            self.update_pp_display()
        
        self.window.after(100, self.update_display)

if __name__ == "__main__":
    try:
        import cv2
    except ImportError:
        import subprocess
        subprocess.check_call(["pip", "install", "opencv-python", "pillow", "numpy", "pydirectinput"])
        import cv2
    
    app = BotGUI()
