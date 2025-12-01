/**
 * Main JavaScript for Distributed Cloud Storage System
 */

// System status monitoring
let systemStatus = {
    nodes: 0,
    storage: 0,
    files: 0,
    status: 'loading'
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Update system status
    updateSystemStatus();
    
    // Setup file upload handlers
    setupFileUpload();
    
    // Setup real-time updates via WebSocket
    setupWebSocket();
    
    // Periodic updates
    setInterval(updateSystemStatus, 10000); // Update every 10 seconds
});

// Update system status display
async function updateSystemStatus() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.status === 'success') {
            systemStatus = {
                nodes: data.active_nodes || 0,
                storage: formatBytes(data.total_available || 0),
                files: data.total_files || 0,
                status: 'healthy'
            };
            
            // Update UI
            const statusEl = document.getElementById('system-status');
            const nodeCountEl = document.getElementById('node-count');
            const storageEl = document.getElementById('storage-usage');
            
            if (statusEl) {
                const statusIcon = statusEl.querySelector('i');
                statusIcon.style.color = '#48bb78'; // Green for healthy
                statusEl.innerHTML = `<i class="fas fa-circle"></i> System Healthy`;
            }
            
            if (nodeCountEl) {
                nodeCountEl.textContent = `Nodes: ${systemStatus.nodes}`;
            }
            
            if (storageEl) {
                storageEl.textContent = `Storage: ${systemStatus.storage} available`;
            }
        }
    } catch (error) {
        console.error('Failed to update system status:', error);
        systemStatus.status = 'error';
        
        const statusEl = document.getElementById('system-status');
        if (statusEl) {
            const statusIcon = statusEl.querySelector('i');
            statusIcon.style.color = '#e53e3e'; // Red for error
            statusEl.innerHTML = `<i class="fas fa-circle"></i> Connection Error`;
        }
    }
}

// Format bytes to human readable format
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Setup file upload functionality
function setupFileUpload() {
    const fileInput = document.getElementById('fileInput');
    const uploadArea = document.getElementById('uploadArea');
    
    if (!fileInput || !uploadArea) return;
    
    // Drag and drop handlers
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFiles(files);
        }
    });
    
    // File input change handler
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });
    
    // Click to browse
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });
}

// Handle file uploads
async function handleFiles(files) {
    for (let file of files) {
        await uploadSingleFile(file);
    }
}

// Upload a single file
async function uploadSingleFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    // Show progress indicator
    showUploadProgress(file.name, 0);
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showUploadProgress(file.name, 100);
            showNotification(`File "${file.name}" uploaded successfully!`, 'success');
            
            // Update file list
            setTimeout(updateFileList, 1000);
        } else {
            throw new Error(result.message || 'Upload failed');
        }
    } catch (error) {
        showUploadProgress(file.name, 0, true);
        showNotification(`Upload failed: ${error.message}`, 'error');
    }
}

// Show upload progress
function showUploadProgress(filename, progress, error = false) {
    // Create or update progress element
    let progressEl = document.getElementById(`progress-${filename}`);
    
    if (!progressEl) {
        progressEl = document.createElement('div');
        progressEl.id = `progress-${filename}`;
        progressEl.className = 'upload-progress-item';
        progressEl.innerHTML = `
            <div class="progress-info">
                <span class="filename">${filename}</span>
                <span class="progress-text">${progress}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progress}%"></div>
            </div>
        `;
        
        const progressContainer = document.querySelector('.upload-progress-container') ||
                                 createProgressContainer();
        progressContainer.appendChild(progressEl);
    } else {
        const progressFill = progressEl.querySelector('.progress-fill');
        const progressText = progressEl.querySelector('.progress-text');
        
        progressFill.style.width = `${progress}%`;
        progressFill.style.backgroundColor = error ? '#e53e3e' : 
                                progress === 100 ? '#38a169' : '#667eea';
        progressText.textContent = error ? 'Failed' : `${progress}%`;
    }
    
    // Remove progress element when complete
    if (progress === 100 || error) {
        setTimeout(() => {
            if (progressEl.parentNode) {
                progressEl.parentNode.removeChild(progressEl);
            }
        }, 3000);
    }
}

// Create progress container if it doesn't exist
function createProgressContainer() {
    const container = document.createElement('div');
    container.className = 'upload-progress-container';
    document.querySelector('.upload-section').appendChild(container);
    return container;
}

// Update file list
async function updateFileList() {
    try {
        const response = await fetch('/api/files');
        const data = await response.json();
        
        if (data.status === 'success') {
            renderFileList(data.files || []);
        }
    } catch (error) {
        console.error('Failed to update file list:', error);
    }
}

// Render file list
function renderFileList(files) {
    const filesList = document.getElementById('filesList');
    if (!filesList) return;
    
    if (files.length === 0) {
        filesList.innerHTML = '<div class="empty-state">No files uploaded yet</div>';
        return;
    }
    
    filesList.innerHTML = files.map(file => `
        <div class="file-item" data-file-id="${file.file_id}">
            <div class="file-icon">
                <i class="fas fa-${getFileIcon(file.original_filename)}"></i>
            </div>
            <div class="file-info">
                <div class="file-name">${file.original_filename}</div>
                <div class="file-meta">
                    <span>${file.size_human}</span>
                    <span>${new Date(file.upload_time * 1000).toLocaleDateString()}</span>
                    <span>${file.replica_count} replicas</span>
                </div>
            </div>
            <div class="file-actions">
                <button class="btn-download" onclick="downloadFile('${file.file_id}')">
                    <i class="fas fa-download"></i>
                </button>
                <button class="btn-delete" onclick="deleteFile('${file.file_id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

// Get file icon based on extension
function getFileIcon(filename) {
    const extension = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'pdf': 'file-pdf',
        'doc': 'file-word',
        'docx': 'file-word',
        'txt': 'file-alt',
        'jpg': 'file-image',
        'jpeg': 'file-image',
        'png': 'file-image',
        'gif': 'file-image',
        'mp4': 'file-video',
        'avi': 'file-video',
        'mov': 'file-video',
        'mp3': 'file-audio',
        'wav': 'file-audio',
        'zip': 'file-archive',
        'rar': 'file-archive',
        '7z': 'file-archive'
    };
    
    return iconMap[extension] || 'file';
}

// Download file
async function downloadFile(fileId) {
    try {
        showNotification('Starting download...', 'info');
        
        const response = await fetch(`/api/download/${fileId}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            // Create download link
            const link = document.createElement('a');
            link.href = data.download_url;
            link.download = data.file_info.original_filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showNotification('Download started!', 'success');
        } else {
            throw new Error(data.message || 'Download failed');
        }
    } catch (error) {
        showNotification(`Download failed: ${error.message}`, 'error');
    }
}

// Delete file
async function deleteFile(fileId) {
    if (!confirm('Are you sure you want to delete this file?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/delete/${fileId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showNotification('File deleted successfully!', 'success');
            setTimeout(updateFileList, 1000);
        } else {
            throw new Error(data.message || 'Delete failed');
        }
    } catch (error) {
        showNotification(`Delete failed: ${error.message}`, 'error');
    }
}

// Setup WebSocket for real-time updates
function setupWebSocket() {
    const socket = io();
    
    socket.on('connect', () => {
        console.log('Connected to WebSocket server');
    });
    
    socket.on('file_uploaded', (data) => {
        showNotification(`New file uploaded: ${data.filename}`, 'success');
        updateFileList();
        updateSystemStatus();
    });
    
    socket.on('file_deleted', (data) => {
        showNotification('File deleted', 'info');
        updateFileList();
        updateSystemStatus();
    });
    
    socket.on('system_update', (data) => {
        if (data.status === 'success') {
            // Update storage info
            const storageEl = document.querySelector('.storage-info');
            if (storageEl) {
                const usedPercent = (data.total_used / data.total_capacity * 100).toFixed(1);
                storageEl.innerHTML = `
                    <div class="storage-bar">
                        <div class="storage-used" style="width: ${usedPercent}%"></div>
                    </div>
                    <div class="storage-text">
                        ${formatBytes(data.total_used)} / ${formatBytes(data.total_capacity)} (${usedPercent}%)
                    </div>
                `;
            }
        }
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from WebSocket server');
    });
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${getNotificationIcon(type)}"></i>
        <span>${message}</span>
    `;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Remove after 5 seconds
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Get notification icon based on type
function getNotificationIcon(type) {
    const icons = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// Initialize storage visualization
function initStorageVisualization() {
    const storageEl = document.querySelector('.storage-visualization');
    if (!storageEl) return;
    
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const usedPercent = (data.total_used / data.total_capacity * 100).toFixed(1);
                
                storageEl.innerHTML = `
                    <div class="storage-chart">
                        <div class="chart-bar">
                            <div class="chart-used" style="height: ${usedPercent}%"></div>
                        </div>
                        <div class="chart-labels">
                            <span>Used: ${formatBytes(data.total_used)}</span>
                            <span>Free: ${formatBytes(data.total_capacity - data.total_used)}</span>
                        </div>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Failed to load storage data:', error);
        });
}

// Export functions for use in templates
window.downloadFile = downloadFile;
window.deleteFile = deleteFile;