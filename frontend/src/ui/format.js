export const money = (minor, currency = 'INR') => new Intl.NumberFormat('en-IN', {style: 'currency', currency}).format(minor / 100);
export const tripDate = value => new Intl.DateTimeFormat('en-IN', {day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC'}).format(new Date(value + 'T00:00:00Z'));
