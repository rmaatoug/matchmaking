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

            // First row contains anesthesiologist names (starting from column 2)
            const headerRow = rows[0];
            anesthesiologistColumns = [];

            for (let i = 0; i < headerRow.length; i++) {
                const value = headerRow[i];
                // Check if it looks like a doctor name
                if (value && (value.startsWith('Dr') || value.startsWith('Dr.'))) {
                    anesthesiologistColumns[i] = value;
                }
            }

            // Process each date row (starting from row 1)
            for (let rowIndex = 1; rowIndex < rows.length; rowIndex++) {
                const row = rows[rowIndex];

                // Column 0 = day name, Column 1 = date
                const dateStr = row[1];

                // Validate date format (DD/MM/YYYY)
                if (!dateStr || !/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
                    continue;
                }

                // Initialize date entry if needed
                if (!scheduleData[dateStr]) {
                    scheduleData[dateStr] = {};
                }

                // Process surgeon assignments (columns 2+)
                for (let colIndex = 2; colIndex < row.length; colIndex++) {
                    const surgeonName = row[colIndex];
                    const anesthesiologist = anesthesiologistColumns[colIndex];

                    if (surgeonName && anesthesiologist) {
                        // Clean up surgeon name
                        const cleanSurgeon = surgeonName.trim();
                        if (cleanSurgeon && cleanSurgeon.startsWith('Dr')) {
                            scheduleData[dateStr][cleanSurgeon] = anesthesiologist;
                            surgeonList.add(cleanSurgeon);
                        }
                    }
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

            if (!scheduleData[frenchDate]) {
                return { found: false, error: 'date_not_found', date: frenchDate };
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

            return { found: false, error: 'surgeon_not_found', date: frenchDate, surgeon };
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
                messageDiv.innerHTML = `
                    <strong>Important :</strong> Prenez rendez-vous sur Doctolib avec
                    ${anesthDisplay} pour votre consultation
                    pré-opératoire. C'est cet anesthésiste qui vous endormira le jour de votre opération.
                `;
            } else {
                resultDiv.classList.add('result-error');
                if (result.error === 'date_not_found') {
                    nameDiv.textContent = 'Date non trouvée';
                    messageDiv.textContent = `Aucune information disponible pour le ${result.date}. Veuillez contacter la clinique.`;
                } else {
                    nameDiv.textContent = 'Non trouvé';
                    messageDiv.textContent = `Le chirurgien ${result.surgeon} n'a pas d'opération prévue le ${result.date}. Veuillez vérifier vos informations.`;
                }
            }
        }

        // Initialize the application
        async function init() {
            try {
                // Reset data (important when reloading / re-initializing)
                scheduleData = {};
                surgeonList = new Set();
                anesthesiologistColumns = [];

                // Fetch live data from Google Sheets (no cache)
                const url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRCFMw2RRGRxRGNtMW4QQ2-0YPjfVtLd6QFQU5p2IEI1qa_K0liTEeRGwLKmjH3WKNYvOSy0kFaY4cU/pub?gid=1693056628&output=csv';
                const response = await fetch(url + '&_=' + Date.now(), { cache: 'no-store' });

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
