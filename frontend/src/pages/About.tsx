import { Link } from "react-router-dom";
import { Reveal } from "../components/Reveal";
import OrbitImages from "../components/effects/OrbitImages";
import bayOfBengalMap from "../assets/orbit/bay-of-bengal-map.jpg";
import cycloneFani from "../assets/orbit/cyclone-fani.jpg";
import argoFloat from "../assets/orbit/argo-float.jpg";
import incois from "../assets/orbit/incois.jpg";
import puriFishingBoats from "../assets/orbit/puri-fishing-boats.jpg";
import ctdCast from "../assets/orbit/ctd-cast.jpg";

const ORBIT_IMAGES = [
  {
    src: bayOfBengalMap,
    link: "https://en.wikipedia.org/wiki/Bay_of_Bengal",
    label: "The Bay of Bengal: the region VARUNA is scope-locked to",
  },
  {
    src: cycloneFani,
    link: "https://en.wikipedia.org/wiki/Cyclone_Fani",
    label: "Cyclone Fani (2019): the kind of fast-moving extreme event VARUNA needs to help catch early",
  },
  {
    src: argoFloat,
    link: "https://argo.ucsd.edu/",
    label: "An Argo float being deployed: real in-situ data VARUNA fuses against the model",
  },
  {
    src: incois,
    link: "https://incois.gov.in/",
    label: "INCOIS: the Indian Ocean forecast source VARUNA validates against",
  },
  {
    src: puriFishingBoats,
    link: "https://incois.gov.in/OSF/index.jsp",
    label: "Fishing boats at Puri, Odisha: who a tool like this is ultimately for",
  },
  {
    src: ctdCast,
    link: "https://en.wikipedia.org/wiki/CTD_(instrument)",
    label: "A CTD rosette being deployed: another real sensor type VARUNA ingests",
  },
];

export function About() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-32">
      <Reveal>
        <p className="font-nav text-xs opacity-60">Our mission</p>
        <h1 className="font-display mt-3 text-5xl sm:text-6xl">About VARUNA</h1>
        <p className="mt-6 max-w-2xl text-lg opacity-80">
          Two versions of the ocean exist today: the one physics models forecast, and the one real
          sensors measure. Nobody has put them in the same room and asked them to agree. VARUNA
          does, continuously, in a browser, for anyone who needs to trust the water.
        </p>
      </Reveal>

      <Reveal className="mt-16">
        <h2 className="font-display text-3xl">What VARUNA does</h2>
        <p className="mt-4 max-w-2xl text-sm opacity-75">
          It fuses INCOIS-class ocean model forecasts with real Argo, glider, CTD and buoy
          readings using a graph of real sensor connectivity, then actively flags where the model
          and reality disagree instead of leaving that comparison to manual, periodic desktop
          work. The result renders as a live 3D digital twin, not a static report.{" "}
          <Link to="/services" className="underline" style={{ color: "var(--color-accent)" }}>
            See how it works
          </Link>
          .
        </p>
      </Reveal>

      <Reveal className="mt-16">
        <h2 className="font-display text-3xl">Built in alignment with</h2>
        <p className="mt-4 max-w-2xl text-sm opacity-75">
          VARUNA's region scope, variable set, and validation approach are built to plug into
          INCOIS's own Indian Ocean Forecast System (INDOFOS) and the Ministry of Earth Sciences'
          broader ocean-safety mandate, not to compete with them. The forecast side of the fusion
          is designed to ingest INCOIS/INDOFOS operational feeds directly; the demo build runs on
          equivalent open reanalysis data (Copernicus GLORYS, NOAA HYCOM) where live government
          feeds require authorization outside this project's reach.
        </p>
      </Reveal>

      <Reveal className="mt-24">
        <h2 className="font-display text-3xl">The region, and the problem</h2>
        <p className="mt-4 max-w-xl text-sm opacity-75">
          Click through any image for the real source behind it: the region VARUNA covers, the
          kind of storm it needs to catch early, the real sensors it fuses, and who it's for.
        </p>
        <div className="mt-10 flex justify-center">
          <OrbitImages
            images={ORBIT_IMAGES.map((o) => o.src)}
            links={ORBIT_IMAGES.map((o) => o.link)}
            labels={ORBIT_IMAGES.map((o) => o.label)}
            shape="ellipse"
            baseWidth={760}
            radiusX={330}
            radiusY={210}
            itemSize={92}
            rotation={-6}
            duration={38}
            responsive
            centerContent={
              <p className="font-nav max-w-[10rem] text-center text-[11px] opacity-60">
                Six real sources, one ocean
              </p>
            }
          />
        </div>
        <p className="mt-6 text-center text-[11px] opacity-50">
          Images: NOAA, Ifremer, OOI, Tausheef Hassan Auntu (public domain); Arjuncm3, Braja
          Sorensen (CC BY-SA), via Wikimedia Commons.
        </p>
      </Reveal>

      <Reveal id="who-this-is-for" className="scroll-anchor mt-16">
        <h2 className="font-display text-3xl">Who this is for</h2>
        <p className="mt-4 text-sm opacity-75">
          Fishermen, the Indian Navy, Coast Guard, shipping and offshore operators, coastal disaster
          management authorities, and ocean researchers validating models. The dual expert/public
          mode on the Digital Twin exists specifically so the same tool serves a researcher reading
          raw confidence stats and a fisherman reading a simple safe / caution / avoid signal.
        </p>
      </Reveal>
    </div>
  );
}
