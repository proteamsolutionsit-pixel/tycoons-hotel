import { addDays, guestsLabel, hotelToday, longDate, nightsBetween, rateBreakdown, rupees, stayRange, tariffLine } from '../utils/format';

describe('format helpers', () => {
  it('formats paise as rupees', () => {
    expect(rupees(650000)).toBe('₹6,500');
    expect(rupees(1500000)).toBe('₹15,000');
    expect(rupees(12345)).toBe('₹123.45');
    expect(rupees(null)).toBe('');
  });

  it('does date arithmetic without timezone drift', () => {
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(nightsBetween('2026-03-28', '2026-03-31')).toBe(3);
    expect(longDate('2026-11-02')).toBe('Mon, 2 Nov 2026');
  });

  it('uses the hotel timezone for "today"', () => {
    // 20:00 UTC on 1 Jan is already 2 Jan in Bengaluru
    expect(hotelToday(new Date('2026-01-01T20:00:00Z'))).toBe('2026-01-02');
  });

  it('labels guests', () => {
    expect(guestsLabel(1, 0)).toBe('1 adult');
    expect(guestsLabel(2, 1)).toBe('2 adults, 1 child');
  });
});

describe('stayRange', () => {
  it('stays short enough for one table line', () => {
    expect(stayRange('2026-10-25', '2026-10-26')).toBe('25 – 26 Oct 2026');
    expect(stayRange('2026-10-30', '2026-11-02')).toBe('30 Oct – 2 Nov 2026');
    expect(stayRange('2026-12-30', '2027-01-02')).toBe('30 Dec 2026 – 2 Jan 2027');
    expect(stayRange('', '2026-10-26')).toBe('');
  });
});

describe('occupancy tariffs', () => {
  it('builds the public tariff line', () => {
    expect(tariffLine(450000, 350000, 'Complimentary breakfast')).toBe('Single occupancy ₹3,500 · Double occupancy ₹4,500 · Complimentary breakfast');
    expect(tariffLine(750000, null, '')).toBe('');
    expect(tariffLine(750000, null, 'Breakfast')).toBe('Breakfast');
  });
  it('breaks a price down by occupancy', () => {
    expect(rateBreakdown({ rate: 450000, singleRate: 350000, singles: 1, rooms: 1, nights: 1 })).toBe('₹3,500 (single occupancy) × 1 night');
    expect(rateBreakdown({ rate: 450000, singleRate: 350000, singles: 0, rooms: 1, nights: 2 })).toBe('₹4,500 (double occupancy) × 2 nights');
    expect(rateBreakdown({ rate: 450000, singleRate: 350000, singles: 1, rooms: 2, nights: 2 })).toBe('(₹4,500 double + ₹3,500 single) × 2 nights');
    expect(rateBreakdown({ rate: 650000, singleRate: null, rooms: 2, nights: 1 })).toBe('₹6,500 × 2 rooms × 1 night');
  });
});
