// ===== Model =====
const COLUMNS = [
    { id: 'backlog', name: 'Backlog', wip: null },
    { id: 'inprogress', name: 'In Progress', wip: 4 },
    { id: 'review', name: 'Review', wip: 3 },
    { id: 'done', name: 'Done', wip: null },
];

// API Configuration
// Derive API base from current origin so frontend and backend can share an origin.
const ORIGIN = window.location.origin;
const API_BASE = `${ORIGIN}/api`;

let state = {
    tasks: {}
};

// Authentication state
let currentProfessor = null;
let currentClassId = null;
let classes = [];

// ===== API Functions =====
async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'include' // Include cookies for session management
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    const url = `${API_BASE}${endpoint}`;

    try {
        const response = await fetch(url, options);
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'API request failed');
        }

        return result;
    } catch (error) {
        console.error('API Error:', error);
        // Handle specific Chromium browser errors
        if (error.message && error.message.includes('message port closed')) {
            // Retry the request once
            try {
                const retryResponse = await fetch(url, options);
                const retryResult = await retryResponse.json();
                if (retryResponse.ok) {
                    return retryResult;
                }
            } catch (retryError) {
                console.error('Retry also failed:', retryError);
            }
        }
        throw error;
    }
}

// ===== Authentication =====
async function authenticate(profId, password) {
    try {
        const result = await apiRequest('/auth/login', 'POST', {
            prof_id: profId,
            password: password
        });


        if (result.success) {
            currentProfessor = result.professor;
            return true;
        }
        return false;
    } catch (error) {
        console.error('Login error:', error);
        return false;
    }
}

async function signup(profId, name, password) {
    try {
        const result = await apiRequest('/auth/signup', 'POST', {
            prof_id: profId,
            name: name,
            password: password
        });


        if (result.success) {
            currentProfessor = result.professor;
            return true;
        }
        return false;
    } catch (error) {
        console.error('Signup error:', error);
        return false;
    }
}

async function logout() {
    try {
        await apiRequest('/auth/logout', 'POST');
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        currentProfessor = null;
        updateAuthUI();
    }
}

async function checkAuthStatus() {
    try {
        const result = await apiRequest('/auth/status');
        if (result.authenticated) {
            currentProfessor = result.professor;
            return true;
        }
        return false;
    } catch (error) {
        console.error('Auth status check error:', error);
        return false;
    }
}

function isAuthenticated() {
    return currentProfessor !== null;
}

// ===== DOM =====
const boardEl = document.getElementById('board');
const searchEl = document.getElementById('search');
const addBtn = document.getElementById('addTask');
const uploadSyllabusBtn = document.getElementById('uploadSyllabusBtn');
const syllabusFile = document.getElementById('syllabusFile');
const exportBtn = document.getElementById('exportBtn');
const importBtn = document.getElementById('importBtn');
const importFile = document.getElementById('importFile');
const analyticsBtn = document.getElementById('analyticsBtn');
const analyticsPage = document.getElementById('analyticsPage');
const analyticsTableBody = document.getElementById('analyticsTableBody');
const analyticsTotal = document.getElementById('analyticsTotal');
const backToBoardBtn = document.getElementById('backToBoardBtn');
const boardContainer = document.querySelector('.container');
const profInfo = document.getElementById('profInfo');
const profName = document.getElementById('profName');
const logoutBtn = document.getElementById('logoutBtn');
const loadingSpinner = document.getElementById('loadingSpinner');

// Login page elements
const loginPage = document.getElementById('loginPage');
const loginTabBtn = document.getElementById('loginTabBtn');
const signupTabBtn = document.getElementById('signupTabBtn');
const loginForm = document.getElementById('loginForm');
const signupForm = document.getElementById('signupForm');
const profIdInput = document.getElementById('prof_id');
const profPasswordInput = document.getElementById('prof_password');
const loginBtn = document.getElementById('loginBtn');
const signupProfIdInput = document.getElementById('signup_prof_id');
const signupNameInput = document.getElementById('signup_name');
const signupPasswordInput = document.getElementById('signup_password');
const signupConfirmPasswordInput = document.getElementById('signup_confirm_password');
const createAccountBtn = document.getElementById('createAccountBtn');

const modal = document.getElementById('taskModal');
const m_title = document.getElementById('m_title');
const m_desc = document.getElementById('m_desc');
const m_priority = document.getElementById('m_priority');
const m_due = document.getElementById('m_due');
const m_label = document.getElementById('m_label');
const m_status = document.getElementById('m_status');
const deleteBtn = document.getElementById('deleteBtn');
const cancelBtn = document.getElementById('cancelBtn');
const formEl = modal.querySelector('form');

// Student modal elements
const studentModal = document.getElementById('studentModal');

// Class selector elements
const classSelector = document.getElementById('classSelector');
const addClassBtn = document.getElementById('addClassBtn');
const addClassModal = document.getElementById('addClassModal');
const newClassNameInput = document.getElementById('newClassName');
const saveClassBtn = document.getElementById('saveClassBtn');
const cancelClassBtn = document.getElementById('cancelClassBtn');
const addStudentBtn = document.getElementById('addStudentBtn');
const s_name = document.getElementById('s_name');
const s_roll_no = document.getElementById('s_roll_no');
const s_cia1 = document.getElementById('s_cia1');
const s_cia2 = document.getElementById('s_cia2');
const s_cia3 = document.getElementById('s_cia3');
const s_phone = document.getElementById('s_phone');
const s_comment = document.getElementById('s_comment');
const saveStudentBtn = document.getElementById('saveStudentBtn');
const cancelStudentBtn = document.getElementById('cancelStudentBtn');
const deleteStudentBtn = document.getElementById('deleteStudentBtn');
const studentFormEl = studentModal ? studentModal.querySelector('form') : null;

let editingId = null;
let editingStudentRollNo = null;

// ===== Loading Animation =====
function showLoading() {
    if (loadingSpinner) loadingSpinner.style.display = 'flex';
}

function hideLoading() {
    if (loadingSpinner) loadingSpinner.style.display = 'none';
}

// ===== Authentication UI =====
function updateAuthUI() {
    if (isAuthenticated()) {
        // Hide login page, show board
        if (loginPage) loginPage.style.display = 'none';
        if (boardContainer) boardContainer.style.display = 'flex';
        if (profName) profName.textContent = currentProfessor.name;
        if (profInfo) profInfo.style.display = 'flex';
    } else {
        // Hide board, show login page
        if (boardContainer) boardContainer.style.display = 'none';
        if (loginPage) loginPage.style.display = 'flex';
        if (profInfo) profInfo.style.display = 'none';
    }
}

async function loadClasses() {
    try {
        const result = await apiRequest('/classes', 'GET');

        if (result && result.success && Array.isArray(result.classes)) {
            classes = result.classes;

            if (classSelector) {
                // Clear existing options
                classSelector.innerHTML = '';

                // Add default option
                const defaultOption = document.createElement('option');
                defaultOption.value = '';
                defaultOption.textContent = 'Select Class';
                classSelector.appendChild(defaultOption);

                if (classes.length > 0) {
                    classes.forEach(cls => {
                        const option = document.createElement('option');
                        // Handle object format {id, name}
                        const classId = cls.id || cls[0];
                        const className = cls.name || cls[1] || 'Unknown';

                        if (!classId || !className || className === 'Unknown') {
                            return;
                        }

                        option.value = classId;
                        option.textContent = className;
                        classSelector.appendChild(option);
                    });
                } else {
                }
            } else {
                console.error('classSelector element not found!');
            }
        } else {
            classes = [];
            if (classSelector) {
                classSelector.innerHTML = '<option value="">Select Class</option>';
            }
        }
    } catch (error) {
        console.error('Failed to load classes:', error);
        classes = [];
        if (classSelector) {
            classSelector.innerHTML = '<option value="">Select Class</option>';
        }
    }
}

async function handleLogin() {
    const profId = profIdInput.value.trim();
    const password = profPasswordInput.value;


    if (!profId || !password) {
        alert('Please enter both Professor ID and password');
        return;
    }

    try {
        showLoading();
        const success = await authenticate(profId, password);
        hideLoading();
        if (success) {
            updateAuthUI();
            await loadClasses();
            // Don't load board data on login - let user select a class first
            state.tasks = {};
            render();
            profIdInput.value = '';
            profPasswordInput.value = '';
        } else {
            alert('Invalid Professor ID or password');
            profPasswordInput.value = '';
            profPasswordInput.focus();
        }
    } catch (error) {
        hideLoading();
        alert('Login failed. Please try again.');
        console.error('Login error:', error);
    }
}

async function handleSignup() {
    const profId = signupProfIdInput.value.trim();
    const name = signupNameInput.value.trim();
    const password = signupPasswordInput.value;
    const confirmPassword = signupConfirmPasswordInput.value;


    if (!profId || !name || !password) {
        alert('Please fill in all fields');
        return;
    }

    if (password !== confirmPassword) {
        alert('Passwords do not match');
        signupConfirmPasswordInput.focus();
        return;
    }

    if (password.length < 6) {
        alert('Password must be at least 6 characters long');
        signupPasswordInput.focus();
        return;
    }

    try {
        showLoading();
        const success = await signup(profId, name, password);
        if (success) {
            // After successful signup, log the user in
            const loginSuccess = await authenticate(profId, password);
            hideLoading();

            if (loginSuccess) {
                updateAuthUI();
                // Don't load board data - user needs to select a class first
                state.tasks = {};
                render();
                // Clear form
                signupProfIdInput.value = '';
                signupNameInput.value = '';
                signupPasswordInput.value = '';
                signupConfirmPasswordInput.value = '';
            } else {
                alert('Account created but login failed. Please try logging in manually.');
            }
        } else {
            hideLoading();
            alert('Signup failed. Professor ID might already exist.');
            signupProfIdInput.focus();
        }
    } catch (error) {
        hideLoading();
        alert('Signup failed. Please try again.');
        console.error('Signup error:', error);
    }
}

// ===== Board Data Management =====
async function loadBoardData() {
    // Don't load board data if no class is selected
    if (!currentClassId) {
        state.tasks = {};
        render();
        return;
    }

    try {

        const endpoint = currentClassId ? `/board?class_id=${currentClassId}` : '/board';
        const result = await apiRequest(endpoint);

        // Ensure we have a tasks object
        if (result && result.tasks) {
            state.tasks = result.tasks;
        } else {
            state.tasks = {};
        }

        render();
    } catch (error) {
        console.error('Failed to load board data:', error);
        console.error('Error details:', error.message);
        alert('Failed to load board data. Please try again.');
    }
}

async function saveTask(taskData) {
    try {
        const dataWithClass = currentClassId ? { ...taskData, class_id: currentClassId } : taskData;
        const result = await apiRequest('/board/tasks', 'POST', dataWithClass);
        state.tasks[result.task.id] = result.task;
        render();
        return result.task;
    } catch (error) {
        console.error('Failed to save task:', error);
        alert('Failed to save task. Please try again.');
        throw error;
    }
}

async function updateTask(taskId, taskData) {
    try {
        const dataWithClass = currentClassId ? { ...taskData, class_id: currentClassId } : taskData;
        await apiRequest(`/board/tasks/${taskId}`, 'PUT', dataWithClass);
        state.tasks[taskId] = { ...state.tasks[taskId], ...taskData };
        render();
    } catch (error) {
        console.error('Failed to update task:', error);
        alert('Failed to update task. Please try again.');
        throw error;
    }
}

async function deleteTask(taskId) {
    try {
        const endpoint = currentClassId ? `/board/tasks/${taskId}?class_id=${currentClassId}` : `/board/tasks/${taskId}`;
        await apiRequest(endpoint, 'DELETE');
        delete state.tasks[taskId];
        render();
    } catch (error) {
        console.error('Failed to delete task:', error);
        alert('Failed to delete task. Please try again.');
        throw error;
    }
}

async function moveTask(taskId, newStatus, newOrder) {
    try {
        await apiRequest('/board/tasks/move', 'POST', {
            task_id: taskId,
            status: newStatus,
            order: newOrder,
            class_id: currentClassId
        });
        state.tasks[taskId].status = newStatus;
        state.tasks[taskId].order = newOrder;
        render();
    } catch (error) {
        console.error('Failed to move task:', error);
        alert('Failed to move task. Please try again.');
        throw error;
    }
}

// ===== Rendering =====
function render() {

    if (!isAuthenticated()) {
        return; // Don't render board if not authenticated
    }

    boardEl.innerHTML = '';
    const groups = groupByColumn(filterTasks(Object.values(state.tasks)));
    for (const col of COLUMNS) {
        boardEl.appendChild(columnView(col, groups[col.id] || []));
    }
}

function filterTasks(tasks) {
    const q = (searchEl.value || '').trim().toLowerCase();
    if (!q) return tasks;
    return tasks.filter(t =>
        t.title.toLowerCase().includes(q) ||
        (t.desc || '').toLowerCase().includes(q) ||
        (t.label || '').toLowerCase().includes(q)
    );
}

function groupByColumn(tasks) {
    const g = {}; for (const t of tasks) { (g[t.status] ||= []).push(t); } return g;
}

function columnView(col, tasks) {
    const el = document.createElement('section');
    el.className = 'column';
    el.dataset.column = col.id;
    el.innerHTML = `
<div class="col-head">
    <div class="col-title">${col.name} <span class="badge" data-badge></span></div>
    <button class="btn" data-add>+ Add</button>
</div>
<div class="dropzone" data-dropzone></div>
`;

    const dz = el.querySelector('[data-dropzone]');
    for (const t of tasks) { dz.appendChild(cardView(t)); }

    // counts / WIP
    const badge = el.querySelector('[data-badge]');
    const count = tasks.length;
    badge.textContent = col.wip ? `${count}/${col.wip}` : count;
    badge.classList.toggle('over', !!(col.wip && count > col.wip));

    // events
    el.querySelector('[data-add]').onclick = () => openModal({ status: col.id });

    // dnd events for column (with placeholder)
    const placeholder = document.createElement('div');
    placeholder.className = 'placeholder';

    dz.addEventListener('dragover', e => {
        e.preventDefault(); dz.classList.add('drag-over');
        // Position placeholder
        const y = e.clientY;
        const cards = [...dz.querySelectorAll('.card')].filter(c => !c.classList.contains('dragging'));
        let inserted = false;
        for (const card of cards) {
            const rect = card.getBoundingClientRect();
            if (y < rect.top + rect.height / 2) {
                dz.insertBefore(placeholder, card);
                inserted = true; break;
            }
        }
        if (!inserted) dz.appendChild(placeholder);
    });
    dz.addEventListener('dragleave', () => { dz.classList.remove('drag-over'); });
    dz.addEventListener('drop', async e => {
        e.preventDefault(); dz.classList.remove('drag-over');
        const id = e.dataTransfer.getData('text/plain');
        if (!id) return;
        // WIP enforcement
        const destCount = dz.querySelectorAll('.card').length - (document.querySelector(`[data-id="${id}"]`)?.closest('[data-dropzone]') === dz ? 1 : 0);
        if (col.wip && destCount >= col.wip) {
            flashBadge(badge); return;
        }
        await moveTaskToColumnAtIndex(id, col.id, indexOfChild(dz, placeholder));
        placeholder.remove();
    });

    return el;
}

function indexOfChild(parent, child) {
    const kids = [...parent.children];
    const idx = kids.indexOf(child);
    return idx < 0 ? kids.length : idx;
}

function prioClass(p) {
    if (p === 'high') return 'red';
    if (p === 'med') return 'yellow';
    return 'green';
}

function cardView(t) {
    const el = document.createElement('article');
    el.className = 'card';
    el.draggable = true;
    el.dataset.id = t.id;
    el.innerHTML = `
<h4 class="card-title">${escapeHtml(t.title)}</h4>
<div class="card-meta">
    <span class="pill ${prioClass(t.prio)}">${t.prio}</span>
    ${t.due ? `<span class="pill blue">📅 ${t.due}</span>` : ''}
    ${t.label ? `<span class="pill purple">#${escapeHtml(t.label)}</span>` : ''}
</div>
<div class="card-footer">
    <small class="muted">${escapeHtml(truncate(t.desc || '', 60))}</small>
    <div>
    <button class="icon-btn" data-edit>Edit</button>
    <button class="icon-btn" data-del>Del</button>
    </div>
</div>
`;

    el.addEventListener('dragstart', e => {
        e.dataTransfer.setData('text/plain', t.id);
        e.dataTransfer.effectAllowed = 'move';
        el.classList.add('dragging');
    });
    el.addEventListener('dragend', () => el.classList.remove('dragging'));
    el.querySelector('[data-edit]').onclick = () => openModal(t);
    el.querySelector('[data-del]').onclick = async () => {
        if (confirm('Delete this task?')) {
            await deleteTask(t.id);
        }
    };
    el.addEventListener('dblclick', () => openModal(t));
    return el;
}

// ===== Actions =====
async function moveTaskToColumnAtIndex(id, destCol, index) {
    const t = state.tasks[id]; if (!t) return;

    // Compute new order by re-laying out tasks in destCol with insertion
    const tasksInCol = Object.values(state.tasks).filter(x => x.status === destCol && x.id !== id)
        .sort((a, b) => (a.order || 0) - (b.order || 0));
    tasksInCol.splice(index, 0, t);
    const newOrder = (index + 1) * 1000;

    await moveTask(id, destCol, newOrder);
}

function openModal(task) {
    editingId = task?.id || null;
    m_title.value = task?.title || '';
    m_desc.value = task?.desc || '';
    m_priority.value = task?.prio || 'med';
    m_due.value = task?.due || '';
    m_label.value = task?.label || '';
    m_status.innerHTML = COLUMNS.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    m_status.value = task?.status || 'backlog';
    deleteBtn.style.display = editingId ? 'inline-block' : 'none';
    modal.showModal();
}

async function saveModal() {
    const title = m_title.value.trim(); if (!title) return;
    const obj = {
        title,
        desc: m_desc.value.trim(),
        prio: m_priority.value,
        due: m_due.value || null,
        label: m_label.value.trim(),
        status: m_status.value,
        order: state.tasks[editingId || '']?.order || Date.now()
    };

    try {
        if (editingId) {
            await updateTask(editingId, obj);
        } else {
            await saveTask(obj);
        }
        modal.close();
    } catch (error) {
        console.error('Failed to save task:', error);
    }
}

function truncate(s, n) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '\'': '&#39;' }[c])); }

// ===== Syllabus Upload =====
uploadSyllabusBtn.onclick = () => syllabusFile.click();

syllabusFile.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!currentClassId) {
        alert('Please select a class first');
        e.target.value = '';
        return;
    }

    if (file.type !== 'application/pdf') {
        alert('Please upload a PDF file');
        return;
    }

    if (file.size > 10 * 1024 * 1024) { // 10MB limit
        alert('File size too large. Please upload a file smaller than 10MB');
        return;
    }

    try {
        uploadSyllabusBtn.textContent = '📚 Processing...';
        uploadSyllabusBtn.disabled = true;

        const formData = new FormData();
        formData.append('syllabus', file);
        if (currentClassId) {
            formData.append('class_id', currentClassId);
        }

        const uploadUrl = `${API_BASE}/syllabus/upload`;
        const response = await fetch(uploadUrl, {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });

        const result = await response.json();

        if (result.success) {
            // Reload board data to show new tasks
            await loadBoardData();
            alert(`Syllabus processed! Added ${Object.keys(result.tasks || {}).length} tasks to your board.`);
        } else {
            alert('Failed to process syllabus: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Syllabus upload error:', error);
        alert('Failed to upload syllabus. Please try again.');
    } finally {
        uploadSyllabusBtn.textContent = '📚 Upload Syllabus';
        uploadSyllabusBtn.disabled = false;
        e.target.value = ''; // Clear file input
    }
};

// ===== Export / Import =====
exportBtn.onclick = async () => {
    if (!isAuthenticated()) { alert('Please login first'); return; }
    try {
        exportBtn.textContent = '⬇️ Preparing...';
        exportBtn.disabled = true;
        const exportUrl = `${API_BASE}/board/export` + (currentClassId ? `?class_id=${currentClassId}` : '');
        const res = await fetch(exportUrl, { credentials: 'include' });
        if (!res.ok) throw new Error('Export failed');
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `board_export_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(blobUrl);
    } catch (e) {
        console.error('Export error:', e);
        alert('Failed to export board');
    } finally {
        exportBtn.textContent = '⬇️ Export';
        exportBtn.disabled = false;
    }
};

importBtn.onclick = () => importFile.click();

importFile.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
        importBtn.textContent = '⬆️ Importing...';
        importBtn.disabled = true;
        const text = await file.text();
        const data = JSON.parse(text);
        const importUrl = `${API_BASE}/board/import?mode=merge` + (currentClassId ? `&class_id=${currentClassId}` : '');
        const res = await fetch(importUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        const out = await res.json();
        if (!res.ok) throw new Error(out.error || 'Import failed');
        await loadBoardData();
        alert(`Imported ${out.imported} tasks (${out.mode})`);
    } catch (err) {
        console.error('Import error:', err);
        alert('Failed to import board');
    } finally {
        importBtn.textContent = '⬆️ Import';
        importBtn.disabled = false;
        e.target.value = '';
    }
};

// ===== Student Analytics =====
async function loadStudentAnalytics() {
    if (!analyticsTableBody || !analyticsTotal) {
        console.error('Analytics table elements not found');
        return;
    }
    try {
        analyticsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">Loading...</td></tr>';
        analyticsTotal.textContent = 'Loading...';

        const endpoint = currentClassId ? `/students/analytics?class_id=${currentClassId}` : '/students/analytics';
        const result = await apiRequest(endpoint);

        if (result.success && result.students) {
            analyticsTotal.textContent = `Total Students: ${result.total}`;

            if (result.students.length === 0) {
                analyticsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">No students found</td></tr>';
                return;
            }

            analyticsTableBody.innerHTML = '';
            result.students.forEach(student => {
                const row = document.createElement('tr');
                const cia1Color = student.cia1 >= 50 ? 'var(--green)' : student.cia1 >= 35 ? 'var(--yellow)' : 'var(--red)';
                const cia2Color = student.cia2 >= 50 ? 'var(--green)' : student.cia2 >= 35 ? 'var(--yellow)' : 'var(--red)';
                const cia3Color = student.cia3 >= 50 ? 'var(--green)' : student.cia3 >= 35 ? 'var(--yellow)' : 'var(--red)';

                row.innerHTML = `
                    <td>${escapeHtml(student.roll_no)}</td>
                    <td>${escapeHtml(student.name)}</td>
                    <td style="text-align: center; color: ${cia1Color}; font-weight: 600;">${student.cia1.toFixed(1)}</td>
                    <td style="text-align: center; color: ${cia2Color}; font-weight: 600;">${student.cia2.toFixed(1)}</td>
                    <td style="text-align: center; color: ${cia3Color}; font-weight: 600;">${student.cia3.toFixed(1)}</td>
                    <td style="text-align: center; font-weight: 600;">${escapeHtml(student.grade)}</td>
                    <td style="text-align: center;">
                        <button class="icon-btn edit-student-btn" data-roll="${escapeHtml(student.roll_no)}">Edit</button>
                        <button class="icon-btn del-student-btn" data-roll="${escapeHtml(student.roll_no)}" style="border-color:var(--red);color:#fecaca">Del</button>
                    </td>
                `;
                analyticsTableBody.appendChild(row);
            });
            analyticsTableBody.querySelectorAll('.edit-student-btn').forEach(btn => {
                btn.addEventListener('click', () => openStudentModal(btn.dataset.roll));
            });
            analyticsTableBody.querySelectorAll('.del-student-btn').forEach(btn => {
                btn.addEventListener('click', () => deleteStudentConfirm(btn.dataset.roll));
            });
        } else {
            const errorMsg = result.error || 'Unknown error';
            console.error('Analytics API error:', errorMsg);
            analyticsTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--red);">Error: ${escapeHtml(errorMsg)}</td></tr>`;
            analyticsTotal.textContent = 'Error loading data';
        }
    } catch (error) {
        console.error('Analytics error:', error);
        const errorMsg = error.message || 'Failed to load student data';
        analyticsTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--red);">Error: ${escapeHtml(errorMsg)}</td></tr>`;
        analyticsTotal.textContent = 'Error loading data';
    }
}

analyticsBtn.onclick = async () => {
    if (!isAuthenticated()) {
        alert('Please login first');
        return;
    }
    if (!analyticsPage || !boardContainer) {
        console.error('Analytics elements not found');
        return;
    }
    // Hide board, show analytics with loading
    showLoading();
    boardContainer.style.display = 'none';
    analyticsPage.style.display = 'flex';
    await loadStudentAnalytics();
    hideLoading();
};

if (backToBoardBtn) {
    backToBoardBtn.onclick = () => {
        if (!analyticsPage || !boardContainer) {
            console.error('Analytics elements not found');
            return;
        }
        // Hide analytics, show board with loading
        showLoading();
        setTimeout(() => {
            analyticsPage.style.display = 'none';
            boardContainer.style.display = 'flex';
            hideLoading();
        }, 100);
    };
}

// ===== Class Management =====
if (addClassBtn) {
    addClassBtn.onclick = () => {
        if (addClassModal) {
            addClassModal.showModal();
        }
    };
}

if (saveClassBtn && newClassNameInput) {
    saveClassBtn.onclick = async () => {
        const className = newClassNameInput.value.trim();
        if (!className) {
            alert('Please enter a class name');
            return;
        }
        try {
            showLoading();
            const result = await apiRequest('/classes', 'POST', { name: className });
            hideLoading();

            if (result.success) {
                // Close modal and clear input first
                if (addClassModal) addClassModal.close();
                if (newClassNameInput) newClassNameInput.value = '';

                // Reload classes from server to get the actual class ID
                await loadClasses();

                // Force a small delay to ensure DOM updates
                await new Promise(resolve => setTimeout(resolve, 100));

                // Select the newly created class
                if (result.class && result.class.id && classSelector) {
                    classSelector.value = result.class.id;
                    currentClassId = result.class.id;

                    // Trigger change event to ensure it updates
                    classSelector.dispatchEvent(new Event('change', { bubbles: true }));

                    await loadBoardData();
                } else {
                }

                alert('Class created successfully');
            } else {
                const errorMsg = result.error || 'Failed to create class';
                console.error('Create class failed:', errorMsg);
                alert(errorMsg);
            }
        } catch (error) {
            hideLoading();
            console.error('Failed to create class:', error);
            alert('Failed to create class: ' + error.message);
        }
    };
}

if (cancelClassBtn) {
    cancelClassBtn.onclick = () => {
        if (addClassModal) addClassModal.close();
        if (newClassNameInput) newClassNameInput.value = '';
    };
}

// ===== Student CRUD Functions =====
function openStudentModal(rollNo) {
    // Hide/remove grade field if it exists (in case of cached HTML)
    const gradeField = document.getElementById('s_grade');
    if (gradeField) {
        const gradeRow = gradeField.closest('.modal-row') || gradeField.closest('div');
        if (gradeRow) {
            gradeRow.style.display = 'none';
        } else {
            gradeField.style.display = 'none';
        }
    }

    if (!rollNo) {
        // New student
        editingStudentRollNo = null;
        if (s_name) s_name.value = '';
        if (s_roll_no) s_roll_no.value = '';
        if (s_cia1) s_cia1.value = '';
        if (s_cia2) s_cia2.value = '';
        if (s_cia3) s_cia3.value = '';
        if (s_phone) s_phone.value = '';
        if (s_comment) s_comment.value = '';
        if (deleteStudentBtn) deleteStudentBtn.style.display = 'none';
        if (studentModal) studentModal.showModal();
    } else {
        // Edit existing student - need to fetch student details
        loadStudentDetails(rollNo);
    }
}

async function loadStudentDetails(rollNo) {
    try {
        // Hide grade field if it exists (in case of cached HTML)
        const gradeField = document.getElementById('s_grade');
        if (gradeField) {
            const gradeRow = gradeField.closest('.modal-row') || gradeField.closest('div');
            if (gradeRow) {
                gradeRow.style.display = 'none';
            } else {
                gradeField.style.display = 'none';
            }
        }

        const result = await apiRequest(`/students/${rollNo}`, 'GET');
        if (result.success && result.student) {
            const student = result.student;
            editingStudentRollNo = rollNo;
            if (s_name) s_name.value = student.name;
            if (s_roll_no) s_roll_no.value = student.roll_no;
            if (s_cia1) s_cia1.value = student.cia1;
            if (s_cia2) s_cia2.value = student.cia2;
            if (s_cia3) s_cia3.value = student.cia3;
            if (s_phone) s_phone.value = student.phone || '';
            if (s_comment) s_comment.value = student.comment || '';
            if (deleteStudentBtn) deleteStudentBtn.style.display = 'inline-block';
            if (studentModal) studentModal.showModal();
        } else {
            console.error('Failed to load student - no student data:', result);
            alert('Failed to load student details: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Failed to load student details:', error);
        alert('Failed to load student details: ' + error.message);
    }
}

async function saveStudent() {
    const name = s_name.value.trim();
    if (!name) {
        alert('Please enter student name');
        return;
    }

    // Check if class is selected when adding new student
    if (!editingStudentRollNo && !currentClassId) {
        alert('Please select a class before adding a student');
        return;
    }

    try {
        showLoading();
        const data = {
            name: name,
            cia1: parseFloat(s_cia1.value) || 0,
            cia2: parseFloat(s_cia2.value) || 0,
            cia3: parseFloat(s_cia3.value) || 0,
            phone: s_phone.value.trim(),
            comment: s_comment.value.trim()
        };

        if (s_roll_no.value.trim()) {
            data.roll_no = s_roll_no.value.trim();
        }

        let result;
        if (editingStudentRollNo) {
            result = await apiRequest(`/students/${editingStudentRollNo}`, 'PUT', data);
        } else {
            const endpoint = currentClassId ? `/students?class_id=${currentClassId}` : '/students';
            result = await apiRequest(endpoint, 'POST', data);
        }

        hideLoading();
        if (result.success) {
            // Reload analytics first to show the new/updated student
            await loadStudentAnalytics();
            if (studentModal) studentModal.close();
            alert(result.message || 'Student saved successfully');
        } else {
            alert(result.error || 'Failed to save student');
        }
    } catch (error) {
        hideLoading();
        console.error('Failed to save student:', error);
        alert('Failed to save student: ' + error.message);
    }
}

function deleteStudentConfirm(rollNo) {
    if (confirm(`Delete student with Roll No. ${rollNo}?`)) {
        deleteStudent(rollNo);
    }
}

async function deleteStudent(rollNo) {
    try {
        showLoading();
        const result = await apiRequest(`/students/${rollNo}`, 'DELETE');
        hideLoading();
        if (result.success) {
            await loadStudentAnalytics();
            alert(result.message || 'Student deleted successfully');
        }
    } catch (error) {
        hideLoading();
        console.error('Failed to delete student:', error);
        alert('Failed to delete student');
    }
}

// Make functions globally accessible for onclick handlers
window.openStudentModal = openStudentModal;
window.deleteStudentConfirm = deleteStudentConfirm;

if (addStudentBtn) {
    addStudentBtn.onclick = () => openStudentModal(null);
}

if (saveStudentBtn) {
    saveStudentBtn.addEventListener('click', (e) => {
        e.preventDefault();
        saveStudent();
    });
}

if (cancelStudentBtn) {
    cancelStudentBtn.addEventListener('click', () => {
        if (studentModal) studentModal.close();
    });
}

if (deleteStudentBtn) {
    deleteStudentBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (editingStudentRollNo && confirm('Delete this student?')) {
            await deleteStudent(editingStudentRollNo);
            if (studentModal) studentModal.close();
        }
    });
}

if (studentFormEl) {
    studentFormEl.addEventListener('submit', (e) => {
        e.preventDefault();
        saveStudent();
    });
}

if (studentModal) {
    studentModal.addEventListener('click', (e) => {
        if (e.target === studentModal) studentModal.close();
    });
}

// ===== Event bindings =====
// Authentication events
loginBtn.addEventListener('click', handleLogin);
logoutBtn.addEventListener('click', logout);
profPasswordInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleLogin(); });
profIdInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') profPasswordInput.focus(); });

// Tab switching
if (loginTabBtn && signupTabBtn && loginForm && signupForm) {
    loginTabBtn.addEventListener('click', () => {
        loginTabBtn.classList.add('active');
        signupTabBtn.classList.remove('active');
        loginForm.style.display = 'block';
        signupForm.style.display = 'none';
    });

    signupTabBtn.addEventListener('click', () => {
        signupTabBtn.classList.add('active');
        loginTabBtn.classList.remove('active');
        signupForm.style.display = 'block';
        loginForm.style.display = 'none';
    });
}

// Signup events
createAccountBtn.addEventListener('click', handleSignup);
signupConfirmPasswordInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSignup(); });
signupPasswordInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') signupConfirmPasswordInput.focus(); });
signupNameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') signupPasswordInput.focus(); });
signupProfIdInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') signupNameInput.focus(); });

// Class selector event
if (classSelector) {
    classSelector.onchange = async () => {
        currentClassId = classSelector.value || null;
        await loadBoardData();
    };
}

// Task events
addBtn.onclick = () => {
    if (!isAuthenticated()) return;
    if (!currentClassId) {
        alert('Please select a class first');
        return;
    }
    openModal({ status: 'backlog' });
};
searchEl.addEventListener('input', render);
document.getElementById('saveBtn').addEventListener('click', (e) => { e.preventDefault(); saveModal(); });
deleteBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    if (editingId && confirm('Delete this task?')) {
        await deleteTask(editingId);
        modal.close();
    }
});
cancelBtn.addEventListener('click', () => modal.close());
// Prevent native validation popup; we gate in saveModal instead
formEl.addEventListener('submit', (e) => { e.preventDefault(); saveModal(); });
// Close modal on backdrop click or Esc
modal.addEventListener('click', (e) => { if (e.target === modal) modal.close(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && modal.open) modal.close(); });

// ===== Initialization =====
async function init() {
    try {
        // Check for existing authentication
        const isAuth = await checkAuthStatus();

        if (isAuth) {
            updateAuthUI();
            await loadClasses();
            // Don't auto-load board - user needs to select a class first
            state.tasks = {};
            render();
        } else {
            updateAuthUI();
        }
    } catch (error) {
        console.error('Initialization error:', error);
        // Show login modal as fallback
        updateAuthUI();
    }
}

// Global error handler
window.addEventListener('error', function (event) {
    console.error('Global error caught:', event.error);
    // Don't let errors break the app
});

// Handle unhandled promise rejections (common in Chromium browsers)
window.addEventListener('unhandledrejection', function (event) {
    console.error('Unhandled promise rejection:', event.reason);
    event.preventDefault(); // Prevent the default error handling
});

// Suppress Chrome extension errors that can break the app
if (typeof chrome !== 'undefined' && chrome.runtime) {
    try {
        chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
            // Handle extension messages gracefully
            return true;
        });
    } catch (e) {
    }
}

// Aggressive protection against extension interference
(function () {
    // Completely override error handling to prevent extension interference
    const originalConsoleError = console.error;
    const originalConsoleWarn = console.warn;

    console.error = function (...args) {
        const message = args.join(' ');
        // Block all extension-related errors
        if (message.includes('message port closed') ||
            message.includes('runtime.lastError') ||
            message.includes('Extension context invalidated') ||
            message.includes('Unchecked runtime.lastError') ||
            message.includes('chrome-extension://')) {
            return; // Completely ignore these errors
        }
        originalConsoleError.apply(console, args);
    };

    console.warn = function (...args) {
        const message = args.join(' ');
        // Block extension warnings too
        if (message.includes('chrome-extension://') ||
            message.includes('runtime.lastError')) {
            return;
        }
        originalConsoleWarn.apply(console, args);
    };

    // Override window.onerror to catch extension errors
    window.onerror = function (message, source, lineno, colno, error) {
        if (message && (message.includes('message port closed') ||
            message.includes('runtime.lastError') ||
            message.includes('chrome-extension://'))) {
            return true; // Prevent default error handling
        }
        return false;
    };
})();

// Initialize the app with error handling and delay for extension conflicts
function initializeApp() {
    try {
        init();
    } catch (error) {
        console.error('Failed to initialize app:', error);
        // Show login modal as fallback
        updateAuthUI();
    }
}

// Delay initialization to avoid extension conflicts with multiple fallbacks
function startApp() {
    try {
        initializeApp();
    } catch (error) {
        setTimeout(() => {
            try {
                initializeApp();
            } catch (retryError) {
                // Fallback: just show login modal
                updateAuthUI();
            }
        }, 200);
    }
}

// Multiple initialization attempts to handle extension conflicts
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(startApp, 150); // Longer delay for extensions
    });
} else {
    setTimeout(startApp, 150); // Longer delay for extensions
}

// Backup initialization after 1 second if nothing else works
setTimeout(() => {
    if (!currentProfessor && loginPage && loginPage.style.display !== 'none') {
        try {
            updateAuthUI();
        } catch (e) {
        }
    }
}, 1000);

// ===== UX helpers =====
function flashBadge(badge) {
    badge.classList.add('over');
    setTimeout(() => badge.classList.remove('over'), 800);
}


