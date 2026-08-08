document.addEventListener('DOMContentLoaded', () => {
  const calendar = document.querySelector('[data-scheduler-calendar]');
  if (!calendar) return;

  const apiRoot = '/api/scheduler/';
  const isStudentAccount = calendar.dataset.studentAccount === 'true';
  const grid = document.getElementById('calendar-grid');
  const monthLabel = document.getElementById('calendar-month');
  const copy = document.getElementById('scheduler-calendar-copy');
  const selectedDateLabel = document.getElementById('calendar-selected-date');
  const empty = document.getElementById('calendar-empty');
  const details = document.getElementById('calendar-event-details');
  const monthFormatter = new Intl.DateTimeFormat('en-IN', {month: 'long', year: 'numeric'});
  const dateFormatter = new Intl.DateTimeFormat('en-IN', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'});
  const today = new Date();
  let visibleMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  let selectedDate = dateKey(today);
  let events = [];

  function dateKey(value) {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function dateFromKey(value) {
    const [year, month, day] = value.split('-').map(Number);
    return new Date(year, month - 1, day);
  }

  function text(tag, value, className = '') {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  }

  function eventItemsFor(date) {
    return events
      .filter(event => event.status === 'BOOKED' && event.event_date === date)
      .sort((left, right) => left.start_time.localeCompare(right.start_time));
  }

  function registeredEventItemsFor(dateEvents) {
    return isStudentAccount ? dateEvents.filter(event => event.is_registered) : dateEvents;
  }

  function renderDetails() {
    const date = dateFromKey(selectedDate);
    const dateEvents = eventItemsFor(selectedDate);
    selectedDateLabel.textContent = dateFormatter.format(date);
    details.replaceChildren();
    empty.classList.toggle('d-none', dateEvents.length > 0);
    empty.textContent = dateEvents.length ? '' : 'No events are scheduled for this date.';

    dateEvents.forEach(event => {
      const item = document.createElement('article');
      item.className = 'scheduler-calendar-event';
      const heading = document.createElement('div');
      heading.className = 'scheduler-calendar-event-heading';
      heading.append(text('h4', event.title), text('span', event.event_type.replaceAll('_', ' '), 'badge text-bg-primary'));
      const room = event.booked_room_details?.name || 'Room to be assigned';
      const time = `${event.start_time.slice(0, 5)}–${event.end_time.slice(0, 5)}`;
      const metadata = document.createElement('dl');
      metadata.className = 'scheduler-calendar-event-meta';
      const addDetail = (label, value) => {
        const pair = document.createElement('div');
        pair.append(text('dt', label), text('dd', value));
        metadata.append(pair);
      };
      addDetail('Time', time);
      addDetail('Room', room);
      addDetail('Expected attendees', String(event.expected_strength));
      if (event.registration_deadline) addDetail('Registration closes', new Date(event.registration_deadline).toLocaleString());
      item.append(heading, metadata);
      if (event.purpose) item.append(text('p', event.purpose, 'scheduler-calendar-event-purpose'));
      details.append(item);
    });
  }

  function renderCalendar() {
    monthLabel.textContent = monthFormatter.format(visibleMonth);
    grid.replaceChildren();
    const firstDay = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), 1);
    const trailingDays = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 0).getDate();
    const leadingCells = firstDay.getDay();

    for (let index = 0; index < leadingCells; index += 1) {
      const cell = document.createElement('div');
      cell.className = 'scheduler-calendar-day is-outside';
      grid.append(cell);
    }
    for (let day = 1; day <= trailingDays; day += 1) {
      const date = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), day);
      const key = dateKey(date);
      const dateEvents = eventItemsFor(key);
      const registeredEvents = registeredEventItemsFor(dateEvents);
      const cell = document.createElement('button');
      cell.type = 'button';
      cell.className = 'scheduler-calendar-day';
      if (key === dateKey(today)) cell.classList.add('is-today');
      if (key === selectedDate) cell.classList.add('is-selected');
      if (dateEvents.length) cell.classList.add('has-events');
      if (isStudentAccount && registeredEvents.length) cell.classList.add('has-registered-events');
      cell.setAttribute('role', 'gridcell');
      cell.setAttribute('aria-selected', String(key === selectedDate));
      cell.setAttribute('aria-label', `${dateFormatter.format(date)}${dateEvents.length ? `, ${dateEvents.length} event${dateEvents.length === 1 ? '' : 's'}` : ''}`);
      cell.append(text('span', String(day), 'scheduler-calendar-day-number'));
      const chips = document.createElement('span');
      chips.className = 'scheduler-calendar-chips';
      if (dateEvents.length) {
        const count = isStudentAccount && registeredEvents.length
          ? registeredEvents.length
          : dateEvents.length;
        const label = isStudentAccount && registeredEvents.length
          ? `${count} booked event${count === 1 ? '' : 's'}`
          : `${count} event${count === 1 ? '' : 's'}`;
        const stateClass = isStudentAccount && registeredEvents.length
          ? ' scheduler-calendar-chip--registered'
          : '';
        chips.append(text('span', label, `scheduler-calendar-chip scheduler-calendar-chip--count${stateClass}`));
      }
      cell.append(chips);
      cell.addEventListener('click', () => {
        selectedDate = key;
        renderCalendar();
        renderDetails();
      });
      grid.append(cell);
    }
    // Always render six calendar rows, including blank trailing days. This
    // keeps the month grid stable and matches the reference layout.
    const remainingCells = 42 - grid.children.length;
    for (let index = 0; index < remainingCells; index += 1) {
      const cell = document.createElement('div');
      cell.className = 'scheduler-calendar-day is-outside';
      grid.append(cell);
    }
  }

  async function loadEvents() {
    const endpoint = isStudentAccount ? 'events/campus/?view=student' : 'events/campus/';
    copy.textContent = isStudentAccount
      ? 'Eligible booked events appear on their scheduled dates.'
      : 'All booked campus events appear on their scheduled dates.';
    try {
      const response = await fetch(apiRoot + endpoint, {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error('Unable to load events.');
      events = data;
      renderCalendar();
      renderDetails();
    } catch (error) {
      copy.textContent = 'Unable to load the event calendar right now.';
      empty.textContent = 'Event details are unavailable right now.';
    }
  }

  async function loadUpdates() {
    const list = document.getElementById('scheduler-dashboard-notifications');
    const empty = document.getElementById('scheduler-dashboard-notifications-empty');
    if (!list || !empty) return;

    try {
      const response = await fetch(`${apiRoot}notifications/${isStudentAccount ? '?view=student' : ''}`, {
        credentials: 'same-origin',
      });
      const updates = await response.json();
      if (!response.ok) throw new Error('Unable to load updates.');
      list.replaceChildren();
      empty.classList.toggle('d-none', updates.length > 0);
      updates.forEach(update => {
        const item = document.createElement('article');
        item.className = 'scheduler-item';
        const oldRoom = update.old_room_name ? ` from ${update.old_room_name}` : '';
        const newRoom = update.new_room_name ? ` to ${update.new_room_name}` : '';
        item.append(
          text('strong', update.event_title),
          text('p', `${update.action.replaceAll('_', ' ').toLowerCase()}${oldRoom}${newRoom}`, 'scheduler-item-detail'),
          text('p', new Date(update.created_at).toLocaleString(), 'scheduler-item-meta'),
        );
        list.append(item);
      });
    } catch (error) {
      empty.textContent = 'Reminders and changes are unavailable right now.';
      empty.classList.remove('d-none');
    }
  }

  document.getElementById('calendar-previous').addEventListener('click', () => {
    visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1);
    renderCalendar();
  });
  document.getElementById('calendar-next').addEventListener('click', () => {
    visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1);
    renderCalendar();
  });
  document.getElementById('calendar-today').addEventListener('click', () => {
    visibleMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    selectedDate = dateKey(today);
    renderCalendar();
    renderDetails();
  });

  loadEvents();
  loadUpdates();

  // When a user returns from registering for an event, refresh markers that
  // may have been restored from the browser's back/forward cache.
  window.addEventListener('pageshow', event => {
    if (event.persisted) {
      loadEvents();
      loadUpdates();
    }
  });
});
