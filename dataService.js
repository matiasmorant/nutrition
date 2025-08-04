const dataService = {
    db: null,

    init() {
        this.db = idbKeyval.createStore('food-app-db', 'food-app-store4');
    },

    // --- IndexedDB (Local Storage) Operations ---

    async loadStoredFoods() {
        const foodsArray = await this.get('storedFoods',[]);
        // Convert array to an object map for faster lookups
        return foodsArray.reduce((obj, food) => {
            if (food && food.name) obj[food.name] = food;
            return obj;
        }, {});
    },

    async saveStoredFoods(foodsObject) {
        await this.set('storedFoods', Object.values(foodsObject));
    },

    async get(key,defaultValue) {return await idbKeyval.get(key, this.db) || defaultValue;},
    async set(key, value) {await idbKeyval.set(key, JSON.parse(JSON.stringify(value)), this.db);},

    // --- Fetch External Data Files ---

    async fetchPredefinedDiets() {
        try {
            const response = await fetch('diets.json');
            if (response.ok) return await response.json();
            console.warn('diets.json not found or failed to load.');
            return [];
        } catch (error) {
            console.error('Error loading predefined diets:', error);
            return [];
        }
    },

    async fetchNutrientTree() {
        try {
            const response = await fetch('nutrientTree.txt');
            if (!response.ok) throw new Error('nutrientTree.txt not found');
            const lines = (await response.text()).split('\n');
            const allNutrients = [];
            const defaultDisplayNutrients = [];
            const defaultNutrientTargets = {};

            lines.forEach(line => {
                const trimmedLine = line.trim();
                if (!trimmedLine) return;

                const parts = trimmedLine.split(/—/).map(part => part.trim());
                let nutrientName = parts[0];

                if (nutrientName.startsWith('+')) {
                    nutrientName = nutrientName.substring(1).trim();
                }

                allNutrients.push(nutrientName);

                if (trimmedLine.startsWith('+')) {
                    defaultDisplayNutrients.push(nutrientName);
                    if (parts.length > 1) {
                        const valuePart = parts[1];
                        if (valuePart.includes('–')) {
                            const range = valuePart.split(/–/).map(p => parseFloat(p.trim()));
                            if (range.length === 2 && !isNaN(range[0]) && !isNaN(range[1])) {
                                defaultNutrientTargets[nutrientName] = { min: range[0], max: range[1], isRange: true };
                            }
                        } else {
                            const defaultValue = parseFloat(valuePart);
                            if (!isNaN(defaultValue)) {
                                defaultNutrientTargets[nutrientName] = { min: defaultValue, max: null, isRange: false };
                            }
                        }
                    }
                }
            });
            return { defaultNutrientTargets, allNutrients, defaultDisplayNutrients };
        } catch (error) {
            console.error('Failed to load or parse nutrientTree.txt:', error);
            return { defaultNutrientTargets: {}, allNutrients: [], defaultDisplayNutrients: [] };
        }
    },

    async fetchFoodData() {
        try {
            const response = await fetch('foodnutrient.json');
            if (!response.ok) throw new Error('foodnutrient.json not found');
            const foodData = await response.json();
            if (!Array.isArray(foodData)) throw new Error('Invalid JSON format');

            const nutrientHeaders = new Set();
            foodData.forEach(food => {
                Object.keys(food).forEach(key => {
                    if (key !== 'name') nutrientHeaders.add(key);
                });
            });

            const allFoods = foodData.map(food => {
                nutrientHeaders.forEach(nutrient => {
                    food[nutrient] = parseFloat(food[nutrient]) || 0;
                });
                return food;
            });
            return { allFoods, nutrientHeaders: ['name', ...Array.from(nutrientHeaders)] };
        } catch (error) {
            console.error('Error loading food data:', error);
            alert('Error: Could not load or parse food data.');
            return { allFoods: [], nutrientHeaders: [] };
        }
    },

    async fetchNutrientInfo() {
        try {
            const response = await fetch('nutrientinfo.md');
            if (!response.ok) {
                console.warn('nutrientinfo.md not found.');
                return {};
            }
            const text = await response.text();
            const info = {};
            let currentNutrient = null;
            let currentContent = [];

            text.split('\n').forEach(line => {
                if (line.startsWith('# ')) {
                    if (currentNutrient) {
                        info[currentNutrient] = currentContent.join('<br>').trim();
                    }
                    currentNutrient = line.substring(2).trim();
                    currentContent = [];
                } else if (currentNutrient) {
                    currentContent.push(line);
                }
            });

            if (currentNutrient) {
                info[currentNutrient] = currentContent.join('<br>').trim();
            }
            return info;
        } catch (error) {
            console.error('Failed to load nutrient info:', error);
            return {};
        }
    },
};

// Initialize the service immediately so it's ready for use.
dataService.init();
