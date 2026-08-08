document.addEventListener('DOMContentLoaded', () => {
  const page = document.querySelector('[data-scheduler-page]');
  if (!page) return;

  const apiRoot = '/api/scheduler/';
  const message = document.getElementById('scheduler-message');
  const isStudentAccount = page.dataset.studentAccount === 'true';
  const canBook = page.dataset.canBook === 'true';

  const csrfToken = () => {
    const cookie = document.cookie.split('; ').find(item => item.startsWith('csrftoken='))?.split('=')[1];
    return cookie ? decodeURIComponent(cookie) : document.querySelector('[name=csrfmiddlewaretoken]')?.value;
  };

  const errorMessage = data => {
    if (typeof data === 'string') return data;
    if (!data || typeof data !== 'object') return 'Request failed.';
    return Object.values(data).flat(Infinity).join(' ') || 'Request failed.';
  };

  const request = async (path, options = {}) => {
    const response = await fetch(apiRoot + path, {
      credentials: 'same-origin',
      ...options,
      headers: {'X-CSRFToken': csrfToken(), ...(options.headers || {})},
    });
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new Error(errorMessage(data));
    return data;
  };

  const showMessage = (copy, tone = 'success') => {
    if (!message) return;
    message.textContent = copy;
    message.className = `alert alert-${tone}`;
    message.classList.remove('d-none');
    message.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  };
  const clearMessage = () => message?.classList.add('d-none');
  const text = (tag, value, className = '') => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const setEmpty = (id, visible, copy) => {
    const node = document.getElementById(id);
    if (!node) return;
    if (copy) node.textContent = copy;
    node.classList.toggle('d-none', !visible);
  };
  const time = value => value ? value.slice(0, 5) : '';
  const eventDetail = event => `${event.event_date} | ${time(event.start_time)}–${time(event.end_time)} | ${event.booked_room_details?.name || 'Room pending'}`;
  const statusBadge = status => text('span', status, `badge text-bg-${status === 'BOOKED' ? 'success' : status === 'CANCELLED' ? 'danger' : 'secondary'}`);
  const registrationIsOpen = event => event.status === 'BOOKED' && !event.registration_closed && new Date(event.registration_deadline) > new Date() && new Date(`${event.event_date}T${event.start_time}`) > new Date();
  const actionButton = (label, icon, tone, handler) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `btn btn-sm btn-${tone}`;
    button.append(text('i', '', `bi bi-${icon}`), text('span', label));
    button.addEventListener('click', handler);
    return button;
  };

  const mountBooking = () => {
    const form = document.getElementById('scheduler-form');
    const list = document.getElementById('recommendations');
    const empty = document.getElementById('recommendation-empty');
    const parseBranches = value => value.split(',').map(part => part.trim()).filter(Boolean);
    const parseYears = value => value.split(',').map(part => Number(part.trim())).filter(Number.isInteger);

    const showRecommendations = (recommendations, payload) => {
      list.replaceChildren();
      empty.classList.toggle('d-none', recommendations.length > 0);
      if (!recommendations.length) {
        empty.textContent = 'No active room matches this date, time, capacity, and facilities.';
        return;
      }
      recommendations.forEach(item => {
        const row = document.createElement('article');
        row.className = 'scheduler-item scheduler-room-result';
        const copy = document.createElement('div');
        copy.append(
          text('strong', item.room.name),
          text('p', `${item.room.building || 'Campus'} | Capacity ${item.room.capacity} | ${item.unused_seats} seats free`, 'scheduler-item-detail'),
        );
        const book = actionButton('Book room', 'calendar-check', 'primary', async () => {
          try {
            clearMessage();
            book.disabled = true;
            await request('events/create/', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({...payload, room_id: item.room.id}),
            });
            list.replaceChildren();
            empty.classList.remove('d-none');
            empty.textContent = 'Booking confirmed. Search again for another event.';
            form.reset();
            showMessage('Room booked and event published. Participants have been notified.');
          } catch (error) {
            book.disabled = false;
            showMessage(error.message, 'danger');
          }
        });
        row.append(copy, book);
        list.append(row);
      });
    };

    form.addEventListener('submit', async event => {
      event.preventDefault();
      clearMessage();
      const deadline = document.getElementById('deadline').value;
      const payload = {
        title: document.getElementById('title').value.trim(),
        event_type: document.getElementById('event-type').value,
        purpose: document.getElementById('purpose').value.trim(),
        expected_strength: Number(document.getElementById('strength').value),
        branches: parseBranches(document.getElementById('branches').value),
        years: parseYears(document.getElementById('years').value),
        coordinator_emails: document.getElementById('coordinator-emails').value,
        event_date: document.getElementById('event-date').value,
        start_time: document.getElementById('start-time').value,
        end_time: document.getElementById('end-time').value,
        registration_deadline: new Date(deadline).toISOString(),
        require_projector: document.getElementById('projector').checked,
        require_ac: document.getElementById('ac').checked,
        require_wifi: document.getElementById('wifi').checked,
        require_audio_system: document.getElementById('audio').checked,
        require_smart_board: document.getElementById('smart-board').checked,
      };
      try {
        const data = await request('events/availability/', {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
        });
        showRecommendations(data.recommended_rooms, payload);
      } catch (error) {
        showMessage(error.message, 'danger');
      }
    });
  };

  const mountActivity = () => {
    const list = document.getElementById('my-events');
    const attendeeView = isStudentAccount;
    const editorElement = document.getElementById('booking-editor');
    const editor = editorElement && window.coreui ? new coreui.Modal(editorElement) : null;
    let editingEventId = null;

    const loadActivity = async () => {
      try {
        const events = await request(attendeeView ? 'events/?view=student' : 'events/');
        list.replaceChildren();
        setEmpty('mine-empty', events.length === 0);
        events.forEach(event => {
          const row = document.createElement('article'); row.className = 'scheduler-item';
          const copy = document.createElement('div');
          const heading = document.createElement('div'); heading.className = 'scheduler-item-title';
          heading.append(text('strong', event.title), statusBadge(event.status));
          copy.append(heading, text('p', eventDetail(event), 'scheduler-item-detail'));
          if (event.registered_strength !== undefined) copy.append(text('p', `${event.registered_strength} registered`, 'scheduler-item-meta'));
          row.append(copy);
          const actions = document.createElement('div'); actions.className = 'scheduler-item-actions';
          if (attendeeView && registrationIsOpen(event)) {
            actions.append(actionButton('Unregister', 'person-dash', 'outline-primary', async () => {
              try { await request(`events/${event.id}/unregister/`, {method: 'DELETE'}); await loadActivity(); showMessage('Your registration was cancelled.'); } catch (error) { showMessage(error.message, 'danger'); }
            }));
          }
          if (canBook && !attendeeView && event.status !== 'CANCELLED') {
            actions.append(actionButton('Change', 'pencil-square', 'outline-primary', () => {
              editingEventId = event.id;
              document.getElementById('edit-date').value = event.event_date;
              document.getElementById('edit-strength').value = event.expected_strength;
              document.getElementById('edit-start').value = time(event.start_time);
              document.getElementById('edit-end').value = time(event.end_time);
              editor?.show();
            }));
            actions.append(actionButton('Cancel', 'x-circle', 'outline-danger', async () => {
              if (!window.confirm(`Cancel ${event.title}?`)) return;
              try { await request(`events/${event.id}/cancel/`, {method: 'POST'}); await loadActivity(); showMessage('Booking cancelled and registered students notified.'); } catch (error) { showMessage(error.message, 'danger'); }
            }));
          }
          if (actions.childElementCount) row.append(actions);
          list.append(row);
        });
      } catch (error) {
        setEmpty('mine-empty', true, 'Unable to load your events.');
      }
    };

    document.getElementById('booking-editor-form')?.addEventListener('submit', async event => {
      event.preventDefault();
      try {
        await request(`events/${editingEventId}/reschedule/`, {
          method: 'PATCH', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({event_date: document.getElementById('edit-date').value, expected_strength: Number(document.getElementById('edit-strength').value), start_time: document.getElementById('edit-start').value, end_time: document.getElementById('edit-end').value}),
        });
        editor?.hide();
        await loadActivity();
        showMessage('Booking updated and the best available room recalculated.');
      } catch (error) { showMessage(error.message, 'danger'); }
    });
    loadActivity();
  };

  const mountCampus = () => {
    const list = document.getElementById('campus-events');
    const attendeeView = isStudentAccount;
    const loadCampus = async () => {
      try {
        const events = await request(attendeeView ? 'events/campus/?view=student' : 'events/campus/');
        const visibleEvents = attendeeView ? events.filter(event => !event.is_registered) : events;
        list.replaceChildren();
        setEmpty('campus-empty', visibleEvents.length === 0);
        visibleEvents.forEach(event => {
          const row = document.createElement('article'); row.className = 'scheduler-item';
          const copy = document.createElement('div');
          const heading = document.createElement('div'); heading.className = 'scheduler-item-title';
          heading.append(text('strong', event.title), statusBadge(event.status));
          copy.append(heading, text('p', eventDetail(event), 'scheduler-item-detail'));
          row.append(copy);
          if (attendeeView) {
            const actions = document.createElement('div'); actions.className = 'scheduler-item-actions';
            if (event.registration_open) {
              actions.append(actionButton('Register', 'person-plus', 'outline-primary', async () => {
                try { await request(`events/${event.id}/register/`, {method: 'POST'}); await loadCampus(); showMessage('You are registered for this event.'); } catch (error) { showMessage(error.message, 'danger'); }
              }));
            } else {
              const closed = actionButton('Registration closed', 'lock', 'outline-secondary', () => {}); closed.disabled = true; actions.append(closed);
            }
            row.append(actions);
          }
          list.append(row);
        });
      } catch (error) { setEmpty('campus-empty', true, 'Unable to load campus events.'); }
    };
    loadCampus();
  };

  const mountRooms = () => {
    const form = document.getElementById('room-form');
    const list = document.getElementById('room-list');
    const loadRooms = async () => {
      try {
        const rooms = await request('rooms/');
        list.replaceChildren();
        setEmpty('rooms-empty', rooms.length === 0);
        rooms.forEach(room => {
          const row = document.createElement('article'); row.className = 'scheduler-item';
          const facilities = ['has_projector', 'has_ac', 'has_wifi', 'has_audio_system', 'has_smart_board'].filter(key => room[key]).length;
          row.append(text('strong', room.name), text('p', `${room.building || 'Campus'}${room.floor ? ` · ${room.floor}` : ''} · Capacity ${room.capacity} · ${facilities ? `${facilities} facilities` : 'No facilities listed'}`, 'scheduler-item-detail'), text('p', room.is_active ? 'Available for booking' : 'Unavailable for booking', 'scheduler-item-meta'));
          list.append(row);
        });
      } catch (error) { setEmpty('rooms-empty', true, 'Unable to load rooms.'); }
    };
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const payload = {
        name: document.getElementById('room-name').value.trim(), building: document.getElementById('room-building').value.trim(), floor: document.getElementById('room-floor').value.trim(), capacity: Number(document.getElementById('room-capacity').value),
        has_projector: document.getElementById('room-projector').checked, has_ac: document.getElementById('room-ac').checked, has_wifi: document.getElementById('room-wifi').checked, has_audio_system: document.getElementById('room-audio').checked, has_smart_board: document.getElementById('room-smart-board').checked, is_active: document.getElementById('room-active').checked,
      };
      try { await request('rooms/', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}); form.reset(); document.getElementById('room-active').checked = true; await loadRooms(); showMessage('Room added successfully.'); } catch (error) { showMessage(error.message, 'danger'); }
    });
    loadRooms();
  };

  const mountTimetable = () => {
    const form = document.getElementById('timetable-form');
    const roomSelect = document.getElementById('timetable-room');
    const list = document.getElementById('timetable-list');
    const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const loadRooms = async () => {
      const rooms = await request('rooms/');
      roomSelect.replaceChildren(text('option', 'Select a room'));
      roomSelect.firstChild.value = '';
      rooms.forEach(room => { const option = text('option', room.name); option.value = room.id; roomSelect.append(option); });
    };
    const loadEntries = async () => {
      try {
        const entries = await request('timetable/');
        list.replaceChildren(); setEmpty('timetable-empty', entries.length === 0);
        entries.forEach(entry => {
          const row = document.createElement('article'); row.className = 'scheduler-item';
          row.append(text('strong', entry.subject || `${entry.branch} Year ${entry.year}`), text('p', `${entry.room_name} · ${dayNames[entry.day_of_week]} · ${time(entry.start_time)}–${time(entry.end_time)}`, 'scheduler-item-detail'), text('p', `${entry.branch} · Year ${entry.year}`, 'scheduler-item-meta'));
          list.append(row);
        });
      } catch (error) { setEmpty('timetable-empty', true, 'Unable to load timetable entries.'); }
    };
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const payload = {room: Number(roomSelect.value), day_of_week: Number(document.getElementById('timetable-day').value), start_time: document.getElementById('timetable-start').value, end_time: document.getElementById('timetable-end').value, branch: document.getElementById('timetable-branch').value.trim(), year: Number(document.getElementById('timetable-year').value), subject: document.getElementById('timetable-subject').value.trim()};
      try { await request('timetable/', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}); form.reset(); await loadEntries(); showMessage('Timetable entry added successfully.'); } catch (error) { showMessage(error.message, 'danger'); }
    });
    Promise.all([loadRooms(), loadEntries()]).catch(error => showMessage(error.message, 'danger'));
  };

  const mountAccess = () => {
    const form = document.getElementById('coordinator-form');
    const list = document.getElementById('coordinator-permission-list');
    const loadPermissions = async () => {
      try {
        const permissions = await request('coordinator-permissions/');
        const activePermissions = permissions.filter(permission => permission.is_active);
        list.replaceChildren(); setEmpty('coordinators-empty', activePermissions.length === 0);
        activePermissions.forEach(permission => {
          const row = document.createElement('article'); row.className = 'scheduler-item';
          const revoke = actionButton('Revoke', 'person-dash', 'outline-danger', async () => {
            try { await request(`coordinator-permissions/${permission.id}/`, {method: 'DELETE'}); await loadPermissions(); showMessage(`Booking access removed for ${permission.email}.`); } catch (error) { showMessage(error.message, 'danger'); }
          });
          row.append(text('div', `${permission.name} | ${permission.email}`), revoke); list.append(row);
        });
      } catch (error) { setEmpty('coordinators-empty', true, 'Unable to load coordinator access.'); }
    };
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const email = document.getElementById('coordinator-email').value.trim();
      try { await request('coordinator-permissions/', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email})}); form.reset(); await loadPermissions(); showMessage(`Booking access granted to ${email}.`); } catch (error) { showMessage(error.message, 'danger'); }
    });
    loadPermissions();
  };

  ({booking: mountBooking, activity: mountActivity, campus: mountCampus, rooms: mountRooms, timetable: mountTimetable, access: mountAccess}[page.dataset.schedulerPage])?.();
});
