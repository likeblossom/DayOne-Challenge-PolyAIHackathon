package org.dayone.midwife;

import org.json.*;
import java.util.*;

/** Builds the schema's nested object/array contract without dropping field evidence. */
public final class MobileStructure {
    private MobileStructure(){}
    public static JSONObject build(JSONObject schema,JSONObject flat)throws Exception{return fields(schema,flat,"");}
    private static JSONObject fields(JSONObject specs,JSONObject flat,String prefix)throws Exception {
        JSONObject result=new JSONObject();
        for(Iterator<String> it=specs.keys();it.hasNext();){String key=it.next();result.put(key,value(specs.getJSONObject(key),flat,prefix+key));}
        return result;
    }
    private static Object value(JSONObject spec,JSONObject flat,String path)throws Exception {
        String type=spec.getString("type");
        if(type.equals("object"))return fields(spec.getJSONObject("fields"),flat,path+".");
        if(type.equals("array")&&spec.getJSONObject("items").getString("type").equals("object")){
            int count=0;String prefix=path+"[";
            for(Iterator<String> it=flat.keys();it.hasNext();){String key=it.next();if(key.startsWith(prefix)){int end=key.indexOf(']',prefix.length());if(end>0)count=Math.max(count,Integer.parseInt(key.substring(prefix.length(),end))+1);}}
            JSONArray rows=new JSONArray();for(int i=0;i<count;i++)rows.put(fields(spec.getJSONObject("items").getJSONObject("fields"),flat,path+"["+i+"]."));return rows;
        }
        JSONObject f=flat.optJSONObject(path);
        if(f==null){
            f=MobileGrammar.field(null,0);
            JSONObject nature=path.endsWith(".other_description")?flat.optJSONObject(path.substring(0,path.lastIndexOf('.')+1)+"nature"):null;
            if(nature!=null&&!nature.isNull("value")&&!"OTHER".equals(nature.optString("value"))){f.put("status","NOT_APPLICABLE").put("confidence",nature.optDouble("confidence")).put("source","detected_non_OTHER_row_has_no_description_cell");}
            else MobileGrammar.issue(f,"NO_PHYSICAL_FIELD_BINDING");
        }
        else f=new JSONObject(f.toString());
        if(!type.equals("array")){try{SchemaCatalog.validateValue(spec,f,path);}catch(IllegalArgumentException e){f.put("rejected_value",f.opt("value")).put("value",JSONObject.NULL);MobileGrammar.issue(f,"SCHEMA_TYPE_OR_RANGE_CONFLICT");}return f;}
        JSONArray values=f.optJSONArray("value"),items=new JSONArray();
        if(values!=null)for(int i=0;i<values.length();i++){JSONObject item=new JSONObject(f.toString());item.put("value",values.get(i));items.put(item);}
        if(items.length()==0&&!(values!=null&&f.optBoolean("selection_observed")&&f.optString("status").equals("KNOWN"))){f.put("value",JSONObject.NULL);MobileGrammar.issue(f,"CONFIRM_EMPTY_SELECTION");items.put(f);}return items;
    }
}
