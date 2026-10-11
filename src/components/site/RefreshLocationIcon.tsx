type RefreshLocationIconProps = {
  className?: string;
  /** Spin only the arrows; the pin stays upright so it stays readable. */
  spin?: boolean;
};

/**
 * Two circular arrows wrapping a map pin -- "refresh my location".
 *
 * Hand-drawn rather than taken from an icon set: the composite the design
 * calls for (rotate arrows *around* a pin) isn't in lucide/react-icons,
 * and the pin has to be punched through with evenodd so it reads on both
 * the white and the dark nav backgrounds.
 *
 * The arrows and the pin are separate groups on purpose -- when the lookup
 * is running only the arrows turn, and the pin holds still as the anchor
 * the whole glyph is read against.
 */
export function RefreshLocationIcon({
  className,
  spin = false,
}: RefreshLocationIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {/* Rotating group: the two arcs and their arrowheads. */}
      <g
        className={spin ? "animate-spin" : undefined}
        style={{ transformBox: "view-box", transformOrigin: "center" }}
      >
        {/* Top arc, sweeping left -> over the top -> right */}
        <path d="M4.75 8.62A8 8 0 0 1 19.25 8.62" />
        {/* Arrowhead at the right end, pointing down (direction of travel) */}
        <path d="M19.25 11.4 17.1 7.5h4.3Z" fill="currentColor" strokeWidth={1.4} />

        {/* Bottom arc, sweeping right -> under the bottom -> left */}
        <path d="M19.25 15.38A8 8 0 0 1 4.75 15.38" />
        {/* Arrowhead at the left end, pointing up */}
        <path d="M4.75 12.6 2.5 16.5h4.3Z" fill="currentColor" strokeWidth={1.4} />
      </g>

      {/* Static group: the pin, hollowed out with evenodd. */}
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        strokeWidth={1.5}
        d="M12 8.2c-1.6 0-2.9 1.3-2.9 2.9 0 2.1 2.9 5.3 2.9 5.3s2.9-3.2 2.9-5.3c0-1.6-1.3-2.9-2.9-2.9Zm0 4.05a1.15 1.15 0 1 0 0-2.3 1.15 1.15 0 0 0 0 2.3Z"
      />
    </svg>
  );
}
