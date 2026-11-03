const currencyFormatters = new Map();
const tripDateFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

export function money(minor, currency = "INR") {
  if (!currencyFormatters.has(currency)) {
    currencyFormatters.set(
      currency,
      new Intl.NumberFormat("en-IN", { style: "currency", currency }),
    );
  }
  return currencyFormatters.get(currency).format(minor / 100);
}

export const tripDate = (value) =>
  tripDateFormatter.format(new Date(value + "T00:00:00Z"));
