        // Data storage
        let scheduleData = {}; // { "DD/MM/YYYY": { "Dr. Surgeon": "Dr. Anesthesiologist" } }
        let surgeonList = new Set();
        let anesthesiologistColumns = []; // Maps column index to anesthesiologist name

        // Doctolib links for anesthesiologists
        const doctolibLinks = {
            "Dr. Aupetit": "https://www.doctolib.fr/anesthesiste/lyon/clemence-aupetit",
            "Dr. Caillierez": "https://www.doctolib.fr/anesthesiste/lyon/romain-caillierez",
            "Dr. Cuche": "https://www.doctolib.fr/anesthesiste/lyon/henri-cuche",
            "Dr. Favre Felix": "https://www.doctolib.fr/anesthesiste/lyon/jeremy-favre-felix",
            "Dr. Maatoug": "https://www.doctolib.fr/anesthesiste/lyon/adel-maatoug",
            "Dr. Mariat": "https://www.doctolib.fr/anesthesiste/lyon/geraldine-mariat",
            "Dr. Reymond": "https://www.doctolib.fr/anesthesiste/lyon/barnabe-reymond",
            "Dr. Rousson": "https://www.doctolib.fr/anesthesiste/lyon/delphine-rousson",
            "Dr. Vaudelin": "https://www.doctolib.fr/anesthesiste/lyon/guillemette-vaudelin"
        };

        // Parse CSV text into rows
        function parseCSV(text) {
            const rows = [];
            let currentRow = [];
            let currentCell = '';
            let insideQuotes = false;

            for (let i = 0; i < text.length; i++) {
                const char = text[i];
                const nextChar = text[i + 1];

                if (char === '"') {
                    if (insideQuotes && nextChar === '"') {
                        currentCell += '"';
                        i++;
                    } else {
                        insideQuotes = !insideQuotes;
                    }
                } else if (char === ',' && !insideQuotes) {
                    currentRow.push(currentCell.trim());
                    currentCell = '';
                } else if ((char === '\n' || (char === '\r' && nextChar === '\n')) && !insideQuotes) {
                    currentRow.push(currentCell.trim());
                    if (currentRow.some(cell => cell !== '')) {
                        rows.push(currentRow);
                    }
                    currentRow = [];
                    currentCell = '';
                    if (char === '\r') i++;
                } else if (char !== '\r') {
                    currentCell += char;
                }
            }

            // Don't forget the last cell/row
            if (currentCell || currentRow.length > 0) {
                currentRow.push(currentCell.trim());
                if (currentRow.some(cell => cell !== '')) {
                    rows.push(currentRow);
                }
            }

            return rows;
        }

        // Parse the calendar CSV and build lookup data
        function processCalendarData(rows) {
            if (rows.length < 2) {
                console.error('Not enough rows in CSV');
                return;
            }

            // Adapté pour CSV: date, chirurgien, anesthésiste
            for (let rowIndex = 1; rowIndex < rows.length; rowIndex++) {
                const row = rows[rowIndex];
                if (row.length < 3) continue;
                const dateStr = row[0];
                const surgeonName = row[1];
                const anesthesiologist = row[2];

                // Validation date
                if (!dateStr || !/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
                    continue;
                }
                if (!scheduleData[dateStr]) {
                    scheduleData[dateStr] = {};
                }
                if (surgeonName && anesthesiologist) {
                    const cleanSurgeon = surgeonName.trim();
                    scheduleData[dateStr][cleanSurgeon] = anesthesiologist.trim();
                    surgeonList.add(cleanSurgeon);
                }
            }

            console.log(`Loaded ${Object.keys(scheduleData).length} dates and ${surgeonList.size} surgeons`);
        }

        // Populate the surgeon dropdown
    function populateSurgeonDropdown() {
        const select = document.getElementById('surgeon');

        // Reset dropdown (keep the placeholder option)
        select.innerHTML = '<option value="">-- Sélectionnez un chirurgien --</option>';

        const sortedSurgeons = Array.from(surgeonList).sort((a, b) => {
            const nameA = a.replace(/^Dr\.?\s*/i, '').toLowerCase();
            const nameB = b.replace(/^Dr\.?\s*/i, '').toLowerCase();
            return nameA.localeCompare(nameB, 'fr');
        });

        sortedSurgeons.forEach(surgeon => {
            const option = document.createElement('option');
            option.value = surgeon;
            option.textContent = surgeon;
            select.appendChild(option);
        });
    }

        // Format date from input (YYYY-MM-DD) to French format (DD/MM/YYYY)
        function formatDateToFrench(dateStr) {
            const [year, month, day] = dateStr.split('-');
            return `${day}/${month}/${year}`;
        }

        // Look up the anesthesiologist for a given date and surgeon
        function lookupAnesthesiologist(date, surgeon) {
            const frenchDate = formatDateToFrench(date);

            // Si la date n'existe pas, ou le chirurgien n'est pas trouvé, retourner un anesthésiste aléatoire
            const anesthesiologists = [
                'Dr. Martin', 'Dr. Dubois', 'Dr. Bernard', 'Dr. Thomas', 'Dr. Robert',
                'Dr. Richard', 'Dr. Petit', 'Dr. Durand', 'Dr. Leroy', 'Dr. Moreau'
            ];

            if (!scheduleData[frenchDate]) {
                // Date non trouvée, anesthésiste random
                const randomAnesth = anesthesiologists[Math.floor(Math.random() * anesthesiologists.length)];
                return { found: true, anesthesiologist: randomAnesth, random: true };
            }

            // Try exact match first
            if (scheduleData[frenchDate][surgeon]) {
                return { found: true, anesthesiologist: scheduleData[frenchDate][surgeon] };
            }

            // Try normalized match (handle "Dr." vs "Dr " variations)
            const normalizedSurgeon = surgeon.replace(/^Dr\.?\s*/i, 'Dr. ').trim();
            for (const [key, value] of Object.entries(scheduleData[frenchDate])) {
                const normalizedKey = key.replace(/^Dr\.?\s*/i, 'Dr. ').trim();
                if (normalizedKey === normalizedSurgeon) {
                    return { found: true, anesthesiologist: value };
                }
            }

            // Chirurgien non trouvé, anesthésiste random
            const randomAnesth = anesthesiologists[Math.floor(Math.random() * anesthesiologists.length)];
            return { found: true, anesthesiologist: randomAnesth, random: true };
        }

        // Update the result display
        function updateResult() {
            const dateInput = document.getElementById('surgery-date');
            const surgeonSelect = document.getElementById('surgeon');
            const resultDiv = document.getElementById('result');
            const nameDiv = document.getElementById('anesthesiologist-name');
            const messageDiv = document.getElementById('result-message');

            if (!dateInput.value || !surgeonSelect.value) {
                resultDiv.classList.remove('show', 'result-success', 'result-error');
                return;
            }

            const result = lookupAnesthesiologist(dateInput.value, surgeonSelect.value);
            console.log('ANESTH NAME =', JSON.stringify(result.anesthesiologist));
            
            resultDiv.classList.remove('result-success', 'result-error');
            resultDiv.classList.add('show');

            if (result.found) {
                resultDiv.classList.add('result-success');

                const anesthName = result.anesthesiologist;
                const doctolibUrl = doctolibLinks[anesthName];

                // Create clickable name if Doctolib exists
                const anesthDisplay = doctolibUrl
                    ? `<a href="${doctolibUrl}" target="_blank" rel="noopener noreferrer"><strong>${anesthName}</strong></a>`
                    : `<strong>${anesthName}</strong>`;

                // 🔹 1) Name in the highlighted box (now clickable)
                nameDiv.innerHTML = anesthDisplay;

                // 🔹 2) Name in the explanatory text (also clickable)
                if (result.random) {
                    messageDiv.innerHTML = `
                        <strong>Info :</strong> Aucun planning trouvé, anesthésiste attribué aléatoirement : ${anesthDisplay}.
                    `;
                } else {
                    messageDiv.innerHTML = `
                        <strong>Important :</strong> Prenez rendez-vous sur Doctolib avec
                        ${anesthDisplay} pour votre consultation
                        pré-opératoire. C'est cet anesthésiste qui vous endormira le jour de votre opération.
                    `;
                }
            } else {
                resultDiv.classList.add('result-error');
                nameDiv.textContent = 'Erreur';
                messageDiv.textContent = 'Impossible de trouver un anesthésiste.';
            }
        }

        // Initialize the application
        async function init() {
            try {
                // Reset data (important when reloading / re-initializing)
                scheduleData = {};
                surgeonList = new Set();
                anesthesiologistColumns = [];

                // Fetch local anonymized CSV file
                const response = await fetch('data.csv', { cache: 'no-store' });

                if (!response.ok) {
                    throw new Error('Failed to load schedule data');
                }

                const csvText = await response.text();
                const rows = parseCSV(csvText);
                processCalendarData(rows);
                populateSurgeonDropdown();

                // Hide loading, show form
                document.getElementById('loading').classList.add('hidden');
                document.getElementById('lookup-form').classList.remove('hidden');

                // Add event listeners
                document.getElementById('surgery-date').addEventListener('change', updateResult);
                document.getElementById('surgeon').addEventListener('change', updateResult);

            } catch (e) {
                console.error('Initialization error:', e);

                const details = [
                    `Page: ${location.href}`,
                    `UserAgent: ${navigator.userAgent}`,
                    `Fetch: Google Sheets CSV`,
                    `Erreur: ${String(e)}`
                ].join("\n");

                document.getElementById('loading').innerHTML = `
                    <p style="color: #721c24;">Erreur lors du chargement des données.</p>
                    <p style="color: #666; font-size: 0.85rem; margin-top: 10px;">
                        Veuillez rafraîchir la page ou contacter la clinique.
                    </p>
                    <pre style="white-space:pre-wrap; font-size:12px; opacity:.85; margin-top:12px; text-align:left;">${details}</pre>
                    <p style="color:#666; font-size:0.8rem; margin-top:10px;">
                        Astuce : si cela fonctionne en partage de connexion 4G mais pas sur le Wi-Fi de la clinique,
                        le réseau bloque probablement l'accès à Google Sheets.
                    </p>
                `;
            }
        }
        // Start the app
        init();
