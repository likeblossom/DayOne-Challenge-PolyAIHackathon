package org.dayone.midwife;

import org.json.*;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.time.temporal.*;
import java.util.*;

/** Stable record titles and calendar grouping for the on-device library. */
public final class RecordLibrary {
    private static final String[] IDENTIFIERS={
        "patient_name","woman_name","mother_name","newborn_name","full_name","name",
        "cin","national_id","patient_id","record_code","record_id"
    };
    private static final DateTimeFormatter FALLBACK=DateTimeFormatter.ofPattern("yyyy-MM-dd HH-mm");
    private static final DateTimeFormatter DAY=DateTimeFormatter.ofPattern("EEEE, MMMM d",Locale.getDefault());
    private RecordLibrary(){}

    public static ZonedDateTime captured(JSONObject record) {
        try{return Instant.parse(record.optString("captured_at")).atZone(ZoneId.systemDefault());}
        catch(Exception ignored){return Instant.EPOCH.atZone(ZoneId.systemDefault());}
    }
    public static String title(JSONObject record) {
        JSONObject fields=record.optJSONObject("fields");
        if(fields!=null)for(String wanted:IDENTIFIERS){String found=find(fields,wanted);if(found!=null)return clean(found);}
        return FALLBACK.format(captured(record));
    }
    private static String find(Object node,String wanted) {
        if(node instanceof JSONObject){JSONObject object=(JSONObject)node;
            for(Iterator<String> keys=object.keys();keys.hasNext();){String key=keys.next();Object value=object.opt(key);
                if(key.equalsIgnoreCase(wanted)&&value instanceof JSONObject){JSONObject field=(JSONObject)value;Object raw=field.opt("value");
                    if(raw!=null&&raw!=JSONObject.NULL&&!raw.toString().trim().isEmpty())return raw.toString();}
                String nested=find(value,wanted);if(nested!=null)return nested;
            }
        } else if(node instanceof JSONArray){JSONArray array=(JSONArray)node;for(int i=0;i<array.length();i++){String nested=find(array.opt(i),wanted);if(nested!=null)return nested;}}
        return null;
    }
    private static String clean(String value){String safe=value.trim().replaceAll("[\\r\\n\\t]+"," ").replaceAll("\\s+"," ");return safe.length()>48?safe.substring(0,48):safe;}
    public static String weekKey(JSONObject record){ZonedDateTime z=captured(record);WeekFields w=WeekFields.of(Locale.getDefault());return z.get(w.weekBasedYear())+"-W"+String.format(Locale.ROOT,"%02d",z.get(w.weekOfWeekBasedYear()));}
    public static String weekLabel(JSONObject record){ZonedDateTime z=captured(record);LocalDate start=z.toLocalDate().with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY));return "Week of "+start.format(DateTimeFormatter.ofPattern("MMM d, yyyy",Locale.getDefault()));}
    public static String dayKey(JSONObject record){return captured(record).toLocalDate().toString();}
    public static String dayLabel(JSONObject record){return DAY.format(captured(record));}
}
