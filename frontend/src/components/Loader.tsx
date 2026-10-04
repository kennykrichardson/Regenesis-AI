import { motion } from "framer-motion";

export default function Loader() {
  return (
    <motion.div
      className="loader-screen"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      aria-live="polite"
      aria-label="Reconstructing repository"
    >
      <div className="loader-scene">
        <div className="speeder">
          <span className="speeder-wing">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span className="speeder-body" />
          <span className="speeder-face" />
        </div>
        <div className="long-fazers">
          <i />
          <i />
          <i />
          <i />
        </div>
      </div>

      <div className="loader-copy">
        <span>REGENESIS</span>
        <strong>Reconstructing source</strong>
      </div>
    </motion.div>
  );
}