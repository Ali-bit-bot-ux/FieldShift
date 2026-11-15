"use client";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  ChevronDown,
  CircleHelp,
  Droplets,
  Layers3,
  Leaf,
  MapPin,
  MapPinned,
  Ruler,
  SlidersHorizontal,
  Sprout,
  Wallet,
  Wheat,
} from "lucide-react";
import { presets, priorityKeys, regions } from "@/lib/contract";
import { regionNames, priorityNames, numberText } from "@/lib/labels";
import { usePlanner } from "./Store";

const priorityIcons = [Wheat, Droplets, Sprout, Wallet];
export function FieldCard() {
  const { t, lang, settings, catalog, mode, edit, navigate } = usePlanner();
  const [soilHelp, setSoilHelp] = useState(false);
  const soil = catalog.soils.find((s) => s.id === settings.soil_type)!;
  const areaValid =
    settings.field_area_ha >= 0.1 && settings.field_area_ha <= 50000;
  return (
    <form
      className="sheet entry"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (areaValid) navigate(2);
      }}
    >
      <div className="sheet-title">
        <span className="icon-box">
          <MapPinned />
        </span>
        <h2 data-step-heading tabIndex={-1}>
          {t("Моё поле", "Менің танабым", "My field")}
        </h2>
      </div>
      <p className="intro">
        {t(
          "Укажите, где находится поле и какую площадь занимает.",
          "Танаптың орналасқан жері мен ауданын көрсетіңіз.",
          "Choose the region and enter the size of your field.",
        )}
      </p>
      <div className="field-grid">
        <label>
          <span>
            <MapPin />
            {t("Область", "Облыс", "Region")}
          </span>
          <span className="select-box">
            <select
              value={settings.region}
              onChange={(e) =>
                edit({ region: e.target.value as typeof settings.region })
              }
            >
              {regions.map((r) => (
                <option key={r} value={r}>
                  {regionNames[r][lang]}
                </option>
              ))}
            </select>
            <ChevronDown />
          </span>
        </label>
        <label>
          <span>
            <Ruler />
            {t("Площадь поля", "Танап ауданы", "Field area")}
          </span>
          <span className="unit-input">
            <input
              type="number"
              inputMode="decimal"
              min="0.1"
              max="50000"
              step="any"
              aria-invalid={!areaValid}
              aria-describedby={!areaValid ? "area-error" : undefined}
              value={settings.field_area_ha || ""}
              onChange={(e) => edit({ field_area_ha: Number(e.target.value) })}
            />
            <span>{t("га", "га", "ha")}</span>
          </span>
        </label>
        {!areaValid && (
          <p id="area-error" role="alert" className="error-text wide">
            {t(
              "Введите площадь от 0,1 до 50 000 га.",
              "0,1 мен 50 000 га аралығындағы ауданды енгізіңіз.",
              "Enter an area between 0.1 and 50,000 ha.",
            )}
          </p>
        )}
        <div className="wide">
          <div className="row-between">
            <label htmlFor="soil">
              <Layers3 />
              {t("Тип почвы", "Топырақ түрі", "Soil type")}
            </label>
            <button
              type="button"
              className="link soil-trigger"
              aria-expanded={soilHelp}
              aria-controls="soil-help"
              onClick={() => setSoilHelp(!soilHelp)}
            >
              <CircleHelp size={15} />
              {t("Как выбрать", "Қалай таңдаймын", "How to choose")}
            </button>
          </div>
          <div className="select-box">
            <select
              id="soil"
              value={settings.soil_type}
              onChange={(e) => edit({ soil_type: e.target.value })}
            >
              {catalog.soils.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name[lang]}
                </option>
              ))}
            </select>
            <ChevronDown />
          </div>
          {soilHelp && (
            <div id="soil-help" className="inset-note">
              <strong>
                {t(
                  "Сверьтесь с почвенным паспортом поля.",
                  "Танаптың топырақ паспортына қараңыз.",
                  "Check the soil survey for your field.",
                )}
              </strong>
              <p>
                {soil.texture[lang]}. {soil.risk[lang]}.
              </p>
            </div>
          )}
        </div>
        <fieldset className="wide">
          <legend>
            <CalendarDays />
            {t("Горизонт планирования", "Жоспар мерзімі", "Planning period")}
          </legend>
          <div className="year-options">
            {([3, 4] as const).map((n) => (
              <button
                type="button"
                key={n}
                disabled={mode === "fixture" && n === 3}
                aria-pressed={settings.duration_years === n}
                onClick={() => edit({ duration_years: n })}
              >
                {n} {t("года", "жыл", "years")}
                {settings.duration_years === n && <Check size={16} />}
              </button>
            ))}
          </div>
          {mode === "fixture" && (
            <p className="hint">
              {t(
                "Пример охватывает четыре года. Три года доступны при расчёте для поля.",
                "Мысал төрт жылды қамтиды. Танапқа жеке есеп жасағанда үш жылды таңдауға болады.",
                "The example covers four years. A three-year plan is available with field calculations.",
              )}
            </p>
          )}
        </fieldset>
      </div>
      <div className="form-actions">
        <button type="submit" disabled={!areaValid} className="primary">
          {t(
            "Далее: мои приоритеты",
            "Келесі: басымдықтарым",
            "Next: priorities",
          )}
          <ArrowRight />
        </button>
      </div>
    </form>
  );
}
export function Priorities() {
  const { t, lang, settings, mode, edit, navigate, generate, saved } =
    usePlanner();
  const labels = [
    t("Баланс", "Теңгерім", "Balanced"),
    t("Сохранить влагу", "Ылғалды сақтау", "Conserve water"),
    t("Восстановить почву", "Топырақты қалпына келтіру", "Restore soil"),
  ];
  return (
    <section className="sheet entry">
      <div className="sheet-title">
        <span className="icon-box">
          <SlidersHorizontal />
        </span>
        <h2 data-step-heading tabIndex={-1}>
          {t(
            "Что для вас важнее?",
            "Сіз үшін не маңызды?",
            "What matters most?",
          )}
        </h2>
      </div>
      <p className="intro">
        {t(
          "Выберите готовый набор или настройте важность каждого приоритета от 0 до 100.",
          "Дайын нұсқаны таңдаңыз немесе әр басымдықтың маңызын 0 мен 100 аралығында белгілеңіз.",
          "Choose a preset or set the importance of each priority from 0 to 100.",
        )}
      </p>
      <div className="presets">
        {presets.map((p, i) => (
          <button
            className="chip"
            key={i}
            aria-pressed={priorityKeys.every(
              (k) => p[k] === settings.priorities[k],
            )}
            onClick={() => edit({ priorities: p })}
          >
            {labels[i]}
          </button>
        ))}
      </div>
      <div className="sliders">
        {priorityKeys.map((key, i) => {
          const Icon = priorityIcons[i],
            value = settings.priorities[key];
          return (
            <div key={key}>
              <div className="row-between">
                <label htmlFor={key}>
                  <Icon />
                  {priorityNames[key][lang]}
                </label>
                <output htmlFor={key}>{value}</output>
              </div>
              <input
                id={key}
                type="range"
                min="0"
                max="100"
                value={value}
                style={{ "--fill": value + "%" } as React.CSSProperties}
                onChange={(e) =>
                  edit({
                    priorities: {
                      ...settings.priorities,
                      [key]: Number(e.target.value),
                    },
                  })
                }
              />
            </div>
          );
        })}
      </div>
      {priorityKeys.every((k) => settings.priorities[k] === 0) && (
        <p className="inset-note">
          {t(
            "Все значения равны нулю. Каждому приоритету присвоен вес 25%.",
            "Барлық мән нөлге тең. Әр басымдықтың салмағы 25% болады.",
            "All sliders are at zero. Each priority gets an equal 25% weight.",
          )}
        </p>
      )}
      <div className="form-actions split">
        <button className="link" onClick={() => navigate(1)}>
          <ArrowLeft />
          {t("К полю", "Танапқа оралу", "Back to field")}
        </button>
        <button className="primary" onClick={generate}>
          {mode === "fixture"
            ? t("Посмотреть пример", "Мысалды көру", "View example")
            : saved
              ? t("Открыть план", "Жоспарды ашу", "Open plan")
              : t("Получить план", "Жоспар алу", "Get my plan")}
          <ArrowRight />
        </button>
      </div>
    </section>
  );
}
export function Passport() {
  const { lang, t, settings, catalog } = usePlanner();
  const soil = catalog.soils.find((s) => s.id === settings.soil_type)!;
  return (
    <aside className="passport">
      <div className="passport-head">
        <div className="sheet-title">
          <span className="paper-icon">
            <Sprout />
          </span>
          <h2>{t("Паспорт поля", "Танап паспорты", "Field details")}</h2>
        </div>
        <div className="area-value">
          {numberText(settings.field_area_ha, lang)}{" "}
          <span>{t("га", "га", "ha")}</span>
        </div>
        <div className="passport-caption">
          {t("Площадь поля", "Танап ауданы", "Field area")}
        </div>
      </div>
      <dl>
        {[
          {
            Icon: MapPin,
            title: t("Регион", "Өңір", "Region"),
            value: regionNames[settings.region][lang],
          },
          {
            Icon: Layers3,
            title: t("Почва", "Топырақ", "Soil"),
            value: soil.name[lang],
          },
          {
            Icon: CalendarDays,
            title: t("Планирование", "Жоспарлау", "Planning period"),
            value: settings.duration_years + " " + t("года", "жыл", "years"),
          },
        ].map(({ Icon, title, value }) => (
          <div key={title}>
            <dt>
              <Icon size={18} aria-hidden="true" />
              {title}
            </dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <p className="passport-foot">
        <Leaf size={16} />
        {t(
          "Одно поле на этом устройстве",
          "Осы құрылғыдағы бір танап",
          "One field saved on this device",
        )}
      </p>
    </aside>
  );
}
