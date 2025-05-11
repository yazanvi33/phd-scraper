function togglePlaylistOptions() {
    const inputType = document.getElementById('input_type').value;
    const playlistOptions = document.getElementById('playlist_options');
    playlistOptions.style.display = inputType === 'playlist' ? 'block' : 'none';
    toggleRangeOptions();
}

function toggleRangeOptions() {
    const inputType = document.getElementById('input_type').value;
    const rangeTypeSelect = document.getElementById('range_type');
    const rangeType = rangeTypeSelect ? rangeTypeSelect.value : 'entire';
    const rangeOptions = document.getElementById('range_options');
    const startExtractionBtn = document.getElementById('start_extraction');
    
    rangeOptions.style.display = inputType === 'playlist' && rangeType === 'specific' ? 'block' : 'none';
    
    if (rangeOptions && rangeOptions.style.display === 'block') {
        rangeTypeSelect.disabled = true;
        startExtractionBtn.disabled = true;
        fetchVideoList().finally(() => {
            rangeTypeSelect.disabled = false;
            startExtractionBtn.disabled = false;
        });
    } else {
        document.getElementById('total_videos').textContent = '';
        document.getElementById('video_table').querySelector('tbody').innerHTML = '';
    }
}

let sortDirection = 'asc'; // متغير لتتبع اتجاه الفرز

function fetchVideoList() {
    const url = document.getElementById('url').value;
    if (!url) {
        alert('Please enter a playlist URL.');
        return Promise.reject(new Error('No URL provided'));
    }

    return fetch('/list_playlist_videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'error') {
            alert(data.message);
            throw new Error(data.message);
        }
        const totalVideos = data.total_videos;
        const videos = data.videos;
        document.getElementById('total_videos').textContent = `Found ${totalVideos} videos in the playlist.`;
        renderTable(videos);
    })
    .catch(error => {
        console.error('Error fetching video list:', error);
        alert('Error fetching video list: ' + error.message);
        throw error;
    });
}

function renderTable(videos) {
    const tbody = document.getElementById('video_table').querySelector('tbody');
    tbody.innerHTML = '';
    videos.forEach(video => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><input type="checkbox" value="${video.index}" class="video-checkbox"></td>
            <td>${video.index}</td>
            <td>${video.title}</td>
        `;
        tbody.appendChild(row);
    });
}

function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('select_all');
    const checkboxes = document.querySelectorAll('.video-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
}

function sortTable() {
    const tbody = document.getElementById('video_table').querySelector('tbody');
    const rows = Array.from(tbody.getElementsByTagName('tr'));
    
    rows.sort((a, b) => {
        const indexA = parseInt(a.cells[1].textContent);
        const indexB = parseInt(b.cells[1].textContent);
        return sortDirection === 'asc' ? indexA - indexB : indexB - indexA;
    });

    sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';

    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

function startExtraction() {
    const inputType = document.getElementById('input_type').value;
    const url = document.getElementById('url').value;
    const playlistName = document.getElementById('playlist_name').value || '';
    const rangeTypeSelect = document.getElementById('range_type');
    const rangeType = rangeTypeSelect ? rangeTypeSelect.value : 'entire';
    const startIndex = document.getElementById('start_index').value || '';
    const endIndex = document.getElementById('end_index').value || '';
    const progressDiv = document.getElementById('progress');
    const progressBar = document.getElementById('progress-bar');
    const startExtractionBtn = document.getElementById('start_extraction');
    
    progressDiv.textContent = 'Starting extraction...\n';
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';

    if (!url) {
        progressDiv.textContent += 'Error: Please enter a URL.\n';
        alert('Please enter a URL.');
        return;
    }

    startExtractionBtn.disabled = true;
    if (rangeTypeSelect) rangeTypeSelect.disabled = true;

    let selectedIndices = [];
    if (inputType === 'playlist' && rangeType === 'specific') {
        const checkboxes = document.querySelectorAll('.video-checkbox:checked');
        selectedIndices = Array.from(checkboxes).map(cb => cb.value.replace(/^0+/, ''));
    }

    const data = {
        input_type: inputType,
        url: url,
        playlist_name: playlistName,
        range_type: rangeType,
        start_index: startIndex,
        end_index: endIndex,
        selected_indices: selectedIndices
    };

    fetch('/fetch_videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`HTTP error! Status: ${response.status}, Response: ${text.substring(0, 100)}...`);
            });
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const progressLines = [];
        let totalVideos = 1;
        let currentVideo = 0;

        function read() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    startExtractionBtn.disabled = false;
                    if (rangeTypeSelect) rangeTypeSelect.disabled = false;
                    progressBar.style.width = '100%';
                    progressBar.textContent = '100%';
                    return;
                }
                const chunk = decoder.decode(value);
                chunk.split('\n').forEach(line => {
                    if (line) {
                        try {
                            const data = JSON.parse(line);
                            if (data.status === 'progress') {
                                currentVideo = data.current || currentVideo + 1;
                                totalVideos = data.total || totalVideos;
                                const percentage = (currentVideo / totalVideos) * 100;
                                progressBar.style.width = `${percentage}%`;
                                progressBar.textContent = `${Math.round(percentage)}%`;
                                progressLines.unshift(data.message);
                                if (progressLines.length > 5) progressLines.pop();
                                progressDiv.textContent = progressLines.join('\n') + '\n';
                            } else {
                                progressDiv.textContent += data.message + '\n';
                                alert(data.message);
                            }
                            progressDiv.scrollTop = 0;
                        } catch (e) {
                            console.error('Error parsing chunk:', e);
                            progressDiv.textContent += 'Error parsing response: ' + e.message + '\n';
                        }
                    }
                });
                read();
            }).catch(error => {
                console.error('Error reading stream:', error);
                progressDiv.textContent += 'Error reading stream: ' + error.message + '\n';
                alert('Error during extraction: ' + error.message);
                startExtractionBtn.disabled = false;
                if (rangeTypeSelect) rangeTypeSelect.disabled = false;
            });
        }
        read();
    })
    .catch(error => {
        console.error('Error during fetch:', error);
        progressDiv.textContent += 'Error: ' + error.message + '\n';
        alert('Error during extraction: ' + error.message);
        startExtractionBtn.disabled = false;
        if (rangeTypeSelect) rangeTypeSelect.disabled = false;
    });
}