"""Built-in starter knowledge for CHITTI's offline mode (class 6-10 level, English).

Used when no LLM key is set, and as a fallback when school material has nothing on a topic. School-approved resources
always rank first. Each topic: subject, explanation, example, key points, practice MCQs (answer = option index) and
YouTube *search* phrases (we link to YouTube search results, never to invented video ids)."""

TOPICS: dict[str, dict] = {
    "photosynthesis": {
        "title": "Photosynthesis", "subject": "Science", "aliases": ["photo synthesis", "how plants make food", "chlorophyll"],
        "explain": "Photosynthesis is how green plants make their own food. Leaves take in carbon dioxide from the air and "
                   "water from the roots. Using sunlight, captured by the green pigment chlorophyll, they turn these into "
                   "glucose (sugar) and give out oxygen.",
        "example": "A leaf is like a tiny kitchen: sunlight is the stove, water and carbon dioxide are the ingredients, and "
                   "sugar is the food it cooks. Oxygen is the 'steam' that comes out, and we breathe it!",
        "points": ["Word equation: carbon dioxide + water → (sunlight, chlorophyll) → glucose + oxygen",
                   "Happens mainly in the leaves, inside chloroplasts", "Stomata are tiny pores that let gases in and out"],
        "videos": ["photosynthesis for kids", "photosynthesis class 7 explanation"],
        "questions": [
            {"q": "Which gas do plants take in for photosynthesis?", "o": ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"], "a": 1,
             "e": "Plants take in carbon dioxide and give out oxygen."},
            {"q": "What captures sunlight in a leaf?", "o": ["Chlorophyll", "Stomata", "Roots", "Xylem"], "a": 0,
             "e": "Chlorophyll is the green pigment that absorbs light."},
            {"q": "What food does photosynthesis make?", "o": ["Protein", "Fat", "Glucose", "Salt"], "a": 2, "e": "Plants make glucose, a sugar."},
            {"q": "Tiny pores on leaves are called…", "o": ["Veins", "Stomata", "Petals", "Nodes"], "a": 1, "e": "Stomata let gases in and out."},
        ],
    },
    "solar system": {
        "title": "The Solar System & Mars", "subject": "Science",
        "aliases": ["planets", "red planet", "mars", "venus", "jupiter", "sun", "solar"],
        "explain": "The Solar System is the Sun and everything that travels around it: eight planets, their moons, asteroids "
                   "and comets. In order from the Sun: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune. Mars is "
                   "called the Red Planet because iron oxide (rust) in its soil makes it look red.",
        "example": "Remember the order with: 'My Very Educated Mother Just Served Us Nachos'.",
        "points": ["Venus is the hottest planet (thick CO₂ atmosphere traps heat)", "Jupiter is the largest planet",
                   "Mars has the tallest volcano, Olympus Mons", "Earth is the only planet known to have life"],
        "videos": ["solar system for kids", "why is mars red"],
        "questions": [
            {"q": "Which planet is known as the Red Planet?", "o": ["Venus", "Mars", "Jupiter", "Mercury"], "a": 1,
             "e": "Rusty iron oxide dust makes Mars look red. Venus looks bright yellow-white because of its clouds."},
            {"q": "Which is the largest planet?", "o": ["Saturn", "Earth", "Jupiter", "Neptune"], "a": 2, "e": "Jupiter is the biggest."},
            {"q": "Which planet is closest to the Sun?", "o": ["Mercury", "Venus", "Mars", "Earth"], "a": 0, "e": "Mercury is first."},
            {"q": "Why is Venus the hottest planet?", "o": ["It is closest to the Sun", "Its thick atmosphere traps heat",
             "It has volcanoes", "It spins fast"], "a": 1, "e": "Its CO₂ atmosphere causes a strong greenhouse effect."},
        ],
    },
    "fractions": {
        "title": "Fractions", "subject": "Mathematics", "aliases": ["fraction", "numerator", "denominator", "add fractions"],
        "explain": "A fraction shows a part of a whole. The bottom number (denominator) says how many equal parts the whole "
                   "is cut into; the top number (numerator) says how many parts we take. To add fractions, make the "
                   "denominators the same first.",
        "example": "A pizza cut into 8 slices: eating 3 slices means you ate 3/8 of the pizza.",
        "points": ["1/2 + 1/3 = 3/6 + 2/6 = 5/6", "Equivalent fractions: 1/2 = 2/4 = 4/8", "Simplify by dividing top and bottom by the HCF"],
        "videos": ["fractions for kids", "adding fractions with different denominators"],
        "questions": [
            {"q": "What is 1/2 + 1/4?", "o": ["2/6", "3/4", "1/6", "2/4"], "a": 1, "e": "1/2 = 2/4, and 2/4 + 1/4 = 3/4."},
            {"q": "Which fraction equals 1/2?", "o": ["2/3", "3/6", "1/3", "4/6"], "a": 1, "e": "3/6 simplifies to 1/2."},
            {"q": "In 5/8, the denominator is…", "o": ["5", "8", "13", "3"], "a": 1, "e": "The denominator is the bottom number."},
            {"q": "Simplify 6/9", "o": ["2/3", "3/6", "1/3", "6/9"], "a": 0, "e": "Divide both by 3."},
        ],
    },
    "pythagoras theorem": {
        "title": "Pythagoras Theorem", "subject": "Mathematics", "aliases": ["pythagoras", "right triangle", "hypotenuse"],
        "explain": "In a right-angled triangle, the square of the longest side (the hypotenuse) equals the sum of the squares "
                   "of the other two sides: a² + b² = c².",
        "example": "A ladder leans on a wall: the wall is 4 m, the ground gap is 3 m, so the ladder is √(16 + 9) = √25 = 5 m.",
        "points": ["Works only for right-angled triangles", "c is always opposite the right angle", "3-4-5 and 5-12-13 are common triples"],
        "videos": ["pythagoras theorem explained", "pythagoras theorem class 10"],
        "questions": [
            {"q": "Sides 6 and 8 meet at a right angle. Hypotenuse?", "o": ["10", "12", "14", "48"], "a": 0, "e": "√(36+64) = √100 = 10."},
            {"q": "Which is a Pythagorean triple?", "o": ["2,3,4", "5,12,13", "4,5,6", "1,2,3"], "a": 1, "e": "25 + 144 = 169."},
            {"q": "The hypotenuse is opposite the…", "o": ["Smallest angle", "Right angle", "Base", "Height"], "a": 1, "e": "It faces the 90° angle."},
        ],
    },
    "water cycle": {
        "title": "The Water Cycle", "subject": "Science", "aliases": ["evaporation", "condensation", "precipitation", "rain"],
        "explain": "The water cycle is the never-ending journey of water. The Sun heats water so it evaporates into vapour; the "
                   "vapour cools high up and condenses into clouds; when droplets get heavy they fall as precipitation (rain, "
                   "snow); water collects in rivers, lakes and the ground, and the cycle repeats.",
        "example": "Breathe on a cold mirror: the fog you see is condensation, the same thing that makes clouds.",
        "points": ["Evaporation → Condensation → Precipitation → Collection", "Plants also release water (transpiration)"],
        "videos": ["water cycle for kids", "water cycle explanation animation"],
        "questions": [
            {"q": "Water vapour turning into clouds is called…", "o": ["Evaporation", "Condensation", "Melting", "Collection"], "a": 1,
             "e": "Vapour cools and condenses into droplets."},
            {"q": "What gives energy to the water cycle?", "o": ["The Moon", "Wind", "The Sun", "Rocks"], "a": 2, "e": "The Sun heats the water."},
            {"q": "Rain and snow are forms of…", "o": ["Precipitation", "Transpiration", "Evaporation", "Erosion"], "a": 0, "e": "Falling water is precipitation."},
        ],
    },
    "gravity": {
        "title": "Gravity", "subject": "Science", "aliases": ["gravitation", "newton", "force of attraction", "weight"],
        "explain": "Gravity is a pulling force between any two objects that have mass. Earth's gravity pulls things towards its "
                   "centre, which is why a ball falls down and why we have weight. The Moon's gravity causes ocean tides.",
        "example": "Throw a ball up: gravity slows it, stops it and brings it back down to your hands.",
        "points": ["Bigger mass → stronger pull", "Weight = mass × gravity (on Earth g ≈ 9.8 m/s²)", "Your weight on the Moon is about 1/6 of Earth's"],
        "videos": ["gravity for kids", "what is gravity explained simply"],
        "questions": [
            {"q": "Gravity is a…", "o": ["Push force", "Pull force", "Magnetic force", "Friction"], "a": 1, "e": "It pulls objects together."},
            {"q": "On the Moon your weight is…", "o": ["More", "The same", "About 1/6", "Zero"], "a": 2, "e": "The Moon's gravity is weaker."},
            {"q": "Who described the law of gravitation?", "o": ["Edison", "Newton", "Darwin", "Tesla"], "a": 1, "e": "Isaac Newton."},
        ],
    },
    "digestive system": {
        "title": "Human Digestive System", "subject": "Science", "aliases": ["digestion", "stomach", "intestine", "food pipe"],
        "explain": "Digestion breaks food into tiny pieces the body can absorb. Mouth (chewing + saliva) → food pipe "
                   "(oesophagus) → stomach (acid and juices) → small intestine (most absorption) → large intestine (water "
                   "absorbed) → waste leaves the body.",
        "example": "Chewing a chapati for a while makes it taste sweet: saliva is already turning starch into sugar!",
        "points": ["Small intestine is about 6–7 m long", "Liver makes bile to break fats", "Villi increase the area for absorption"],
        "videos": ["digestive system for kids", "human digestive system class 7"],
        "questions": [
            {"q": "Where is most food absorbed?", "o": ["Stomach", "Small intestine", "Large intestine", "Mouth"], "a": 1, "e": "The small intestine, through villi."},
            {"q": "Saliva starts digesting…", "o": ["Proteins", "Fats", "Starch", "Vitamins"], "a": 2, "e": "Saliva has an enzyme for starch."},
            {"q": "Bile is made by the…", "o": ["Liver", "Heart", "Kidney", "Lungs"], "a": 0, "e": "The liver makes bile."},
        ],
    },
    "nouns": {
        "title": "Nouns & Pronouns", "subject": "English", "aliases": ["noun", "pronoun", "parts of speech", "proper noun"],
        "explain": "A noun is a naming word: a person, place, animal, thing or idea (Ravi, Delhi, cat, book, happiness). A "
                   "pronoun takes the place of a noun so we don't repeat it (he, she, it, they, we).",
        "example": "'Meera loves books. She reads them every night.' — She replaces Meera, them replaces books.",
        "points": ["Proper nouns start with a capital letter (India, Monday)", "Common nouns are general names (city, day)",
                   "Collective nouns name groups (a flock of birds)"],
        "videos": ["nouns for kids", "pronouns english grammar for kids"],
        "questions": [
            {"q": "Which word is a proper noun?", "o": ["city", "river", "Ganga", "mountain"], "a": 2, "e": "Ganga is a specific name."},
            {"q": "Pick the pronoun: 'Ali lost his pen.'", "o": ["Ali", "lost", "his", "pen"], "a": 2, "e": "'his' stands for Ali."},
            {"q": "'A ___ of fish' — the collective noun is", "o": ["herd", "school", "pack", "bunch"], "a": 1, "e": "A school of fish."},
        ],
    },
    "tenses": {
        "title": "Tenses", "subject": "English", "aliases": ["tense", "past tense", "present tense", "future tense", "verbs"],
        "explain": "Tense tells us WHEN an action happens. Present: 'I play'. Past: 'I played'. Future: 'I will play'. Each has "
                   "simple, continuous (I am playing), perfect (I have played) and perfect-continuous forms.",
        "example": "Yesterday I walked to school. Today I am walking. Tomorrow I will walk.",
        "points": ["He/she/it + present simple adds -s: she plays", "Irregular past: go → went, eat → ate", "'Will' + base verb = future"],
        "videos": ["tenses for kids english grammar", "present past future tense"],
        "questions": [
            {"q": "Past tense of 'go' is…", "o": ["goed", "gone", "went", "goes"], "a": 2, "e": "Go is irregular: went."},
            {"q": "'She ___ to school every day.'", "o": ["go", "goes", "going", "gone"], "a": 1, "e": "Third person singular adds -es."},
            {"q": "Which sentence is in future tense?", "o": ["I ate lunch", "I eat lunch", "I will eat lunch", "I am eating"], "a": 2, "e": "will + verb."},
        ],
    },
    "linear equations": {
        "title": "Linear Equations", "subject": "Mathematics", "aliases": ["linear equation", "solve for x", "algebra", "equation"],
        "explain": "A linear equation has a variable (like x) with power 1, e.g. 2x + 3 = 11. Solve it by doing the same thing "
                   "to both sides until x is alone: subtract 3 → 2x = 8, divide by 2 → x = 4.",
        "example": "Think of a balance scale: whatever you take off one side, take off the other so it stays balanced.",
        "points": ["Check your answer by putting it back into the equation", "Move terms by doing the inverse operation"],
        "videos": ["solving linear equations for beginners", "linear equations class 8"],
        "questions": [
            {"q": "Solve: x + 7 = 12", "o": ["5", "19", "7", "12"], "a": 0, "e": "Subtract 7 from both sides."},
            {"q": "Solve: 3x = 21", "o": ["18", "7", "24", "63"], "a": 1, "e": "Divide both sides by 3."},
            {"q": "Solve: 2x − 4 = 10", "o": ["3", "7", "6", "14"], "a": 1, "e": "2x = 14, so x = 7."},
        ],
    },
    "area and perimeter": {
        "title": "Area & Perimeter", "subject": "Mathematics", "aliases": ["area", "perimeter", "rectangle", "square"],
        "explain": "Perimeter is the distance around a shape (add all sides). Area is the space inside it, measured in square "
                   "units. Rectangle: perimeter = 2(l + b), area = l × b. Square: perimeter = 4s, area = s².",
        "example": "Fencing a garden needs its perimeter; buying grass for it needs its area.",
        "points": ["Area of triangle = ½ × base × height", "Area of circle = πr², circumference = 2πr"],
        "videos": ["area and perimeter for kids", "area perimeter rectangle square"],
        "questions": [
            {"q": "Area of a 5 cm × 3 cm rectangle?", "o": ["8 cm²", "15 cm²", "16 cm²", "30 cm²"], "a": 1, "e": "5 × 3 = 15."},
            {"q": "Perimeter of a square of side 6 m?", "o": ["24 m", "36 m", "12 m", "18 m"], "a": 0, "e": "4 × 6 = 24."},
            {"q": "Area of a triangle with base 10, height 4?", "o": ["40", "14", "20", "28"], "a": 2, "e": "½ × 10 × 4 = 20."},
        ],
    },
    "electricity": {
        "title": "Electricity & Ohm's Law", "subject": "Science", "aliases": ["ohm", "current", "voltage", "resistance", "circuit"],
        "explain": "Electric current is the flow of charge through a conductor. Voltage (V) pushes the current (I) and resistance "
                   "(R) slows it. Ohm's law: V = I × R. A circuit must be a closed loop for current to flow.",
        "example": "Water in a pipe: voltage is the water pressure, current is how much water flows, resistance is a narrow pipe.",
        "points": ["Units: volt (V), ampere (A), ohm (Ω)", "Series: same current; Parallel: same voltage", "Copper is a good conductor; rubber is an insulator"],
        "videos": ["ohm's law explained", "electric circuit for kids"],
        "questions": [
            {"q": "V = 12 V, R = 4 Ω. Current?", "o": ["3 A", "48 A", "16 A", "8 A"], "a": 0, "e": "I = V/R = 12/4 = 3 A."},
            {"q": "Which is an insulator?", "o": ["Copper", "Iron", "Rubber", "Silver"], "a": 2, "e": "Rubber does not conduct."},
            {"q": "Unit of resistance is…", "o": ["Volt", "Ohm", "Ampere", "Watt"], "a": 1, "e": "Ohm (Ω)."},
        ],
    },
    "cell": {
        "title": "The Cell", "subject": "Science", "aliases": ["cells", "nucleus", "plant cell", "animal cell", "cell structure"],
        "explain": "The cell is the smallest unit of life — all living things are made of cells. Main parts: cell membrane "
                   "(boundary), cytoplasm (jelly where work happens) and nucleus (control centre with DNA). Plant cells also have "
                   "a cell wall, chloroplasts and a big vacuole.",
        "example": "A cell is like a school: the nucleus is the principal's office, the membrane is the gate, the cytoplasm is the corridors.",
        "points": ["Mitochondria release energy (the 'powerhouse')", "Robert Hooke first saw cells in cork (1665)"],
        "videos": ["cell structure for kids", "plant cell vs animal cell"],
        "questions": [
            {"q": "Control centre of the cell?", "o": ["Vacuole", "Nucleus", "Membrane", "Wall"], "a": 1, "e": "The nucleus controls the cell."},
            {"q": "Which is only in plant cells?", "o": ["Nucleus", "Cytoplasm", "Cell wall", "Membrane"], "a": 2, "e": "Animal cells have no cell wall."},
            {"q": "Powerhouse of the cell?", "o": ["Mitochondria", "Ribosome", "Nucleus", "Golgi body"], "a": 0, "e": "Mitochondria release energy."},
        ],
    },
    "democracy": {
        "title": "Democracy", "subject": "Social Studies", "aliases": ["election", "government", "vote", "constitution"],
        "explain": "Democracy is a form of government where people choose their leaders by voting in free and fair elections. "
                   "India is the world's largest democracy; its Constitution came into force on 26 January 1950.",
        "example": "Choosing a class monitor by secret vote is a small democracy.",
        "points": ["Every adult citizen (18+) can vote", "Three organs: legislature, executive, judiciary",
                   "Fundamental rights protect citizens"],
        "videos": ["what is democracy for kids", "indian constitution for kids"],
        "questions": [
            {"q": "Minimum voting age in India?", "o": ["16", "18", "21", "25"], "a": 1, "e": "18 years."},
            {"q": "Indian Constitution came into force on…", "o": ["15 Aug 1947", "26 Jan 1950", "2 Oct 1950", "26 Nov 1949"], "a": 1,
             "e": "Adopted 26 Nov 1949, in force 26 Jan 1950."},
            {"q": "In a democracy leaders are chosen by…", "o": ["Birth", "Voting", "Lottery", "Force"], "a": 1, "e": "Elections."},
        ],
    },
    "acids and bases": {
        "title": "Acids, Bases & Salts", "subject": "Science", "aliases": ["acid", "base", "ph", "litmus", "neutralisation"],
        "explain": "Acids taste sour (lemon juice, vinegar) and turn blue litmus red. Bases taste bitter and feel soapy (baking "
                   "soda, soap) and turn red litmus blue. An acid and a base react to form salt and water: neutralisation.",
        "example": "An antacid tablet (a base) neutralises extra stomach acid.",
        "points": ["pH < 7 acidic, 7 neutral, > 7 basic", "Turmeric turns red in a base", "Never taste chemicals in a lab!"],
        "videos": ["acids and bases for kids", "litmus test experiment"],
        "questions": [
            {"q": "Lemon juice is…", "o": ["Basic", "Acidic", "Neutral", "Salty"], "a": 1, "e": "It is sour: acidic."},
            {"q": "pH of pure water?", "o": ["1", "7", "10", "14"], "a": 1, "e": "Neutral = 7."},
            {"q": "Acid + base →", "o": ["Salt + water", "Only gas", "Metal", "Oil"], "a": 0, "e": "Neutralisation."},
        ],
    },
    "light reflection": {
        "title": "Light & Reflection", "subject": "Science", "aliases": ["reflection", "mirror", "light", "refraction"],
        "explain": "Light travels in straight lines. When it hits a smooth shiny surface like a mirror it bounces back: this is "
                   "reflection. Angle of incidence = angle of reflection. Refraction is the bending of light when it passes "
                   "from one material to another, like air to water.",
        "example": "A straw in a glass of water looks bent: that's refraction!",
        "points": ["Plane mirrors give upright, same-size, laterally inverted images", "Concave mirrors are used in torches"],
        "videos": ["reflection of light for kids", "refraction of light experiment"],
        "questions": [
            {"q": "Angle of incidence = ?", "o": ["Angle of refraction", "Angle of reflection", "90°", "0°"], "a": 1, "e": "Law of reflection."},
            {"q": "A straw looks bent in water due to…", "o": ["Reflection", "Refraction", "Dispersion", "Shadow"], "a": 1, "e": "Light bends."},
            {"q": "Light travels in…", "o": ["Curves", "Circles", "Straight lines", "Zigzags"], "a": 2, "e": "Rectilinear propagation."},
        ],
    },
}


def find(query: str) -> tuple[str, dict] | None:
    q = query.casefold()
    best, score = None, 0
    for key, t in TOPICS.items():
        names = [key, t["title"].casefold(), *[a.casefold() for a in t["aliases"]]]
        s = max((len(n) for n in names if n in q), default=0)
        if s > score:
            best, score = key, s
    return (best, TOPICS[best]) if best else None


def youtube_links(phrases: list[str], lang: str = "en") -> list[dict]:
    from urllib.parse import quote_plus

    lname = {"te": " in telugu", "hi": " in hindi", "ml": " in malayalam", "ta": " in tamil"}.get(lang, "")
    return [{"title": p.title() + lname.title(), "url": f"https://www.youtube.com/results?search_query={quote_plus(p + lname)}"}
            for p in phrases]
