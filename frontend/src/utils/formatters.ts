/**
 * Formats a season number into "S01" format.
 * @param input The raw input string (e.g., "1", "01", "S1")
 * @returns Formatted season code
 */
export const formatSeasonCode = (input: string): string => {
  const digits = input.replace(/\D/g, '');
  if (!digits) return input;
  const num = parseInt(digits, 10);
  return `S${num.toString().padStart(2, '0')}`;
};

/**
 * Formats an episode number into "E01" format.
 * @param input The raw input string (e.g., "1", "01", "E1")
 * @returns Formatted episode code
 */
export const formatEpisodeCode = (input: string): string => {
  const digits = input.replace(/\D/g, '');
  if (!digits) return input;
  const num = parseInt(digits, 10);
  return `E${num.toString().padStart(2, '0')}`;
};
