document.addEventListener('DOMContentLoaded', () => {
    const urlForm = document.getElementById('url-form');
    const urlInput = document.getElementById('video-url');
    const fetchBtn = document.getElementById('fetch-btn');
    const loader = document.getElementById('loader');
    const resultsSection = document.getElementById('results-section');
    const videoTitle = document.getElementById('video-title');
    const videoThumbnail = document.getElementById('video-thumbnail');
    const formatsTable = document.getElementById('formats-table');
    const progressSection = document.getElementById('progress-section');
    const progressStatus = document.getElementById('progress-status');
    const progressBar = document.getElementById('progress-bar');
    const progressDetails = document.getElementById('progress-details');
    const errorMessage = document.getElementById('error-message');

    let currentEventSource = null;

    // --- UTILITY FUNCTIONS ---
    function showLoader() {
        loader.style.display = 'block';
        fetchBtn.disabled = true;
        fetchBtn.textContent = 'Fetching...';
    }

    function hideLoader() {
        loader.style.display = 'none';
        fetchBtn.disabled = false;
        fetchBtn.textContent = 'Fetch Formats';
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }

    function hideAllSections() {
        resultsSection.classList.add('hidden');
        progressSection.classList.add('hidden');
        hideError();
    }

    // --- EVENT HANDLERS ---
    urlForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (!url) {
            showError('Please enter a valid URL.');
            return;
        }

        hideAllSections();
        showLoader();

        try {
            const response = await fetch('/api/get-formats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch formats.');
            }

            displayResults(data);

        } catch (error) {
            showError(error.message);
        } finally {
            hideLoader();
        }
    });

    function displayResults(data) {
        videoTitle.textContent = data.title;
        videoThumbnail.src = data.thumbnail;
        formatsTable.innerHTML = ''; // Clear previous results

        if (data.formats.length === 0) {
            formatsTable.innerHTML = '<tr><td colspan="4">No downloadable video formats found.</td></tr>';
        } else {
            data.formats.forEach(format => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${format.resolution}</td>
                    <td>${format.ext}</td>
                    <td>${format.filesize}</td>
                    <td>
                        <button class="download-btn" data-format-id="${format.format_id}">
                            Download
                        </button>
                    </td>
                `;
                formatsTable.appendChild(row);
            });
        }
        resultsSection.classList.remove('hidden');
    }

    formatsTable.addEventListener('click', (e) => {
        if (e.target.classList.contains('download-btn')) {
            const formatId = e.target.dataset.formatId;
            const url = urlInput.value.trim();
            startDownload(url, formatId);
        }
    });

    function startDownload(url, formatId) {
        // Close any existing connection
        if (currentEventSource) {
            currentEventSource.close();
        }

        hideError();
        progressSection.classList.remove('hidden');
        progressStatus.textContent = "🚀 Starting download...";
        progressBar.style.width = '0%';
        progressDetails.textContent = '';

        // Construct URL with query parameters
        const downloadUrl = `/api/download?url=${encodeURIComponent(url)}&format_id=${encodeURIComponent(formatId)}`;
        currentEventSource = new EventSource(downloadUrl);

        currentEventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);

            switch (data.status) {
                case 'downloading':
                    const percent = parseFloat(data.percent.replace('%', ''));
                    progressStatus.textContent = `Downloading... ${data.percent}`;
                    progressBar.style.width = `${percent}%`;
                    progressDetails.textContent = `Speed: ${data.speed} | ETA: ${data.eta}`;
                    break;
                case 'finished':
                    progressStatus.textContent = data.message;
                    progressBar.style.width = '100%';
                    currentEventSource.close();
                    break;
                case 'error':
                    showError(data.message);
                    progressSection.classList.add('hidden');
                    currentEventSource.close();
                    break;
            }
        };

        currentEventSource.onerror = () => {
            showError('Connection to server lost. Could not get progress.');
            progressSection.classList.add('hidden');
            currentEventSource.close();
        };
    }
});