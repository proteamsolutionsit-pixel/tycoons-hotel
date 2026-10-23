import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import BookingBar from '../components/BookingBar';
import { ContactForm } from '../components/forms/SiteForms';
import { ApiError, request } from '../services/api';
import { addDays, hotelToday } from '../utils/format';

function jsonResponse(status, body) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

function Where() {
  const l = useLocation();
  return <output data-testid="where">{l.pathname + l.search}</output>;
}

describe('api client', () => {
  it('normalises error responses with field details', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(422, {
      error: { code: 'validation_error', message: 'Please check the highlighted fields.', details: [{ field: 'email', message: 'Bad email' }] },
    }));
    const err = await request('/api/x', { method: 'POST', body: {} }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.fieldErrors).toEqual({ email: 'Bad email' });
  });

  it('reports network failures plainly', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    const err = await request('/api/x').catch((e) => e);
    expect(err.code).toBe('network_error');
  });
});

describe('BookingBar', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, [{ slug: 'twin-room', name: 'Twin Room' }]));
  });

  it('refuses a check-out before check-in', async () => {
    const user = userEvent.setup();
    const ci = addDays(hotelToday(), 5);
    const { container } = render(<MemoryRouter><BookingBar /><Where /></MemoryRouter>);
    const [checkin, checkout] = container.querySelectorAll('input[type=date]');
    await user.type(checkin, ci);
    await user.clear(checkout);
    await user.type(checkout, ci);
    await user.click(screen.getByRole('button', { name: 'Check Availability' }));
    expect(await screen.findByText('Must be after check-in')).toBeInTheDocument();
    expect(screen.getByTestId('where').textContent).toBe('/');
  });

  it('opens /book with the stay in the query string', async () => {
    const user = userEvent.setup();
    const ci = addDays(hotelToday(), 5);
    const { container } = render(
      <MemoryRouter><Routes><Route path="*" element={<><BookingBar /><Where /></>} /></Routes></MemoryRouter>,
    );
    const [checkin] = container.querySelectorAll('input[type=date]');
    await user.type(checkin, ci); // check-out defaults to the next day
    await user.selectOptions(container.querySelector('select[name=guests]'), '2-1');
    await user.click(screen.getByRole('button', { name: 'Check Availability' }));
    await waitFor(() => expect(screen.getByTestId('where').textContent)
      .toBe(`/book?check_in=${ci}&check_out=${addDays(ci, 1)}&adults=2&children=1`));
  });
});

describe('ContactForm', () => {
  it('validates before sending, then shows server field errors', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    render(<MemoryRouter><ContactForm /></MemoryRouter>);
    await user.click(screen.getByRole('button', { name: 'Send Enquiry' }));
    expect(await screen.findByText('Please enter your full name')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    fetchMock.mockReturnValue(jsonResponse(422, {
      error: { code: 'validation_error', message: 'Please check the highlighted fields.', details: [{ field: 'email', message: 'That domain does not accept email' }] },
    }));
    await user.type(screen.getByLabelText(/Full name/), 'Asha Rao');
    await user.type(screen.getByLabelText(/^Email/), 'asha@example.com');
    await user.type(screen.getByLabelText(/Message/), 'Hello there');
    await user.click(screen.getByLabelText(/I agree to be contacted/));
    await user.click(screen.getByRole('button', { name: 'Send Enquiry' }));
    expect(await screen.findByText('That domain does not accept email')).toBeInTheDocument();
    expect(screen.getByLabelText(/^Email/)).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows the success message from the API', async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(201, { id: 1, message: "Thank you. We'll be in touch soon." }));
    render(<MemoryRouter><ContactForm /></MemoryRouter>);
    await user.type(screen.getByLabelText(/Full name/), 'Asha Rao');
    await user.type(screen.getByLabelText(/^Email/), 'asha@example.com');
    await user.type(screen.getByLabelText(/Message/), 'Hello there');
    await user.click(screen.getByLabelText(/I agree to be contacted/));
    await user.click(screen.getByRole('button', { name: 'Send Enquiry' }));
    expect(await screen.findByText("Thank you. We'll be in touch soon.")).toBeInTheDocument();
  });
});
