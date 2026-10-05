package org.dayone.midwife;

import android.app.*;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import org.dayone.midwife.model.FieldValue;
import org.json.*;
import java.util.*;

/** Schema-driven editor: nested objects, repeatable rows, enums, all six statuses. */
public final class FormEditor extends Dialog {
    public interface Saved { void accept(JSONObject fields) throws Exception; }
    private interface Read { void run() throws Exception; }
    private final JSONObject specs, data;
    private final Saved saved;
    private final List<Read> readers=new ArrayList<>();
    private LinearLayout body;
    private final String title;
    private final String focusLabel;
    private boolean onlyUncertain;
    public FormEditor(Activity activity,String title,JSONObject specs,JSONObject data,Saved saved) throws JSONException {
        this(activity,title,specs,data,null,saved);
    }
    public FormEditor(Activity activity,String title,JSONObject specs,JSONObject data,String focusLabel,Saved saved) throws JSONException {
        super(activity); this.title=title; this.specs=specs; this.data=new JSONObject(data.toString()); this.focusLabel=focusLabel; this.saved=saved;
    }
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state); requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout root=new LinearLayout(getContext()); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(0xFFF8F8F4); root.setPadding(20,20,20,12);
        TextView heading=text("Review & edit",23); heading.setTypeface(null,android.graphics.Typeface.BOLD); root.addView(heading);
        root.addView(text(title + (focusLabel==null?"":"\n"+focusLabel) + "\nCheck the value against the paper.",14));
        Switch filter=new Switch(getContext()); filter.setText("Only fields needing review"); root.addView(filter);
        if(focusLabel!=null)filter.setVisibility(View.GONE);
        filter.setOnCheckedChangeListener((v,checked) -> { try { flush(); onlyUncertain=checked; render(); } catch(Exception e) { error(e); } });
        ScrollView scroll=new ScrollView(getContext()); body=new LinearLayout(getContext()); body.setOrientation(LinearLayout.VERTICAL); scroll.addView(body);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout actions=new LinearLayout(getContext());
        Button cancel=new Button(getContext()); cancel.setText("Cancel"); cancel.setOnClickListener(v -> dismiss()); actions.addView(cancel,new LinearLayout.LayoutParams(0,-2,1));
        Button save=new Button(getContext()); save.setText("Save changes"); save.setOnClickListener(v -> {
            try { flush(); SchemaCatalog.validateValue(new JSONObject().put("type","object").put("fields",specs),data,""); saved.accept(data); dismiss(); }
            catch(Exception e) { error(e); }
        }); actions.addView(save,new LinearLayout.LayoutParams(0,-2,1)); root.addView(actions);
        setContentView(root); getWindow().setLayout(-1,-1); if(!BuildConfig.DEMO_CAPTURE)getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE); getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        render();
    }
    private TextView text(String s,int size) { TextView t=new TextView(getContext()); t.setText(s); t.setTextSize(size); t.setTextColor(0xFF183D36); t.setPadding(4,10,4,10); return t; }
    private void render() { readers.clear(); body.removeAllViews(); try { object(specs,data,body,""); } catch(Exception e) { error(e); } }
    private void flush() throws Exception { for(Read r:readers) r.run(); }
    private void error(Exception e) { new AlertDialog.Builder(getContext()).setTitle("Check this field").setMessage(e.getMessage()==null?"Invalid field value":e.getMessage()).setPositiveButton("OK",null).show(); }
    private void object(JSONObject fields,JSONObject values,LinearLayout parent,String prefix) throws Exception {
        for(Iterator<String> it=fields.keys();it.hasNext();) {
            String key=it.next(); JSONObject spec=fields.getJSONObject(key);
            node(spec,values.get(key),parent,prefix+SchemaCatalog.label(key));
        }
    }
    private void node(JSONObject spec,Object value,LinearLayout parent,String label) throws Exception {
        String type=spec.getString("type");
        if(focusLabel!=null && !focusLabel.equals(label) && !focusLabel.startsWith(label+" / ") && !focusLabel.startsWith(label+" ")) return;
        if(type.equals("object")) { TextView h=text(label,19); h.setTypeface(null,android.graphics.Typeface.BOLD); parent.addView(h); object(spec.getJSONObject("fields"),(JSONObject)value,parent,label+" / "); return; }
        if(type.equals("array")) {
            JSONArray array=(JSONArray)value; parent.addView(text(label + " · " + array.length() + " entries",18));
            for(int i=0;i<array.length();i++) {
                final int index=i;
                node(spec.getJSONObject("items"),array.get(i),parent,label + " " + (i+1));
                Button remove=new Button(getContext()); remove.setText("Remove " + label.toLowerCase(Locale.ROOT) + " " + (i+1));
                remove.setOnClickListener(v -> { try { flush(); array.remove(index); render(); } catch(Exception e) { error(e); } }); parent.addView(remove);
            }
            Button add=new Button(getContext()); add.setText("+ Add " + label.toLowerCase(Locale.ROOT));
            add.setEnabled(array.length()<spec.optInt("maximum_items",100));
            add.setOnClickListener(v -> { try { flush(); array.put(SchemaCatalog.empty(spec.getJSONObject("items"))); render(); } catch(Exception e) { error(e); } }); parent.addView(add); return;
        }
        JSONObject field=(JSONObject)value;
        boolean uncertain=new SchemaCatalog.Row(label,label,field).needsReview();
        if(onlyUncertain && !uncertain) return;
        TextView name=text(label + (spec.has("unit") ? " ("+spec.getString("unit")+")" : ""),16); name.setTypeface(null,android.graphics.Typeface.BOLD); parent.addView(name);
        String current=field.isNull("value")?"":field.get("value").toString();
        Spinner choice=null; EditText input=null;
        if(type.equals("enum") || type.equals("boolean")) {
            List<String> options=new ArrayList<>(); options.add("— No value —");
            if(type.equals("boolean")) { options.add("true"); options.add("false"); }
            else { JSONArray allowed=spec.getJSONArray("values"); for(int i=0;i<allowed.length();i++) options.add(allowed.getString(i)); }
            choice=spinner(options); choice.setSelection(Math.max(0,options.indexOf(current))); parent.addView(choice);
        } else {
            input=new EditText(getContext()); input.setText(current); input.setTextSize(16); input.setSingleLine(!type.equals("string"));
            input.setHint(type.equals("date")?"YYYY-MM-DD":"Not provided");
            if(type.equals("double") || type.equals("integer")) input.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_SIGNED|(type.equals("double")?InputType.TYPE_NUMBER_FLAG_DECIMAL:0));
            parent.addView(input);
        }
        List<String> statuses=new ArrayList<>(); for(FieldValue.Status status:FieldValue.Status.values()) statuses.add(status.name());
        Spinner status=spinner(statuses); status.setSelection(statuses.indexOf(field.getString("status"))); parent.addView(status);
        TextView confidence=text("Model confidence  " + Math.round(field.optDouble("confidence")*100) + "%" + (uncertain?" · Please check":""),12); confidence.setTextColor(uncertain?0xFF946322:0xFF667972); parent.addView(confidence);
        CheckBox reviewed=new CheckBox(getContext()); reviewed.setText("Checked against the paper"); reviewed.setTextColor(0xFF087F6B); reviewed.setChecked(field.optBoolean("human_reviewed")); parent.addView(reviewed);
        View line=new View(getContext()); line.setBackgroundColor(0xFFDFE5DF); parent.addView(line,new LinearLayout.LayoutParams(-1,1));
        final EditText edit=input; final Spinner select=choice;
        readers.add(() -> {
            String raw=edit!=null ? edit.getText().toString().trim() : select.getSelectedItemPosition()==0 ? "" : select.getSelectedItem().toString();
            Object parsed=JSONObject.NULL;
            try {
                if(!raw.isEmpty()) {
                    switch(type) {
                        case "double": parsed=Double.valueOf(raw); break;
                        case "integer": parsed=Integer.valueOf(raw); break;
                        case "boolean": parsed=Boolean.valueOf(raw); break;
                        default: parsed=raw;
                    }
                }
            } catch(NumberFormatException e) { throw new IllegalArgumentException(label + ": enter a valid " + type); }
            String chosen=status.getSelectedItem().toString();
            boolean changed=!raw.equals(current);
            if(changed && !raw.isEmpty() && chosen.equals(field.optString("status"))) chosen="KNOWN";
            if(raw.isEmpty() && chosen.equals("KNOWN")) chosen="NOT_PROVIDED";
            if(reviewed.isChecked() && !raw.isEmpty() && chosen.equals("NEEDS_REVIEW")) chosen="KNOWN";
            if(changed && !field.has("original_value")) field.put("original_value",field.opt("value"));
            field.put("value",parsed).put("status",chosen).put("human_reviewed",changed||reviewed.isChecked());
            if(changed || reviewed.isChecked()) field.put("reviewed_at",java.time.Instant.now().toString());
            SchemaCatalog.validateValue(spec,field,label);
        });
    }
    private Spinner spinner(List<String> options) {
        Spinner s=new Spinner(getContext()); ArrayAdapter<String> a=new ArrayAdapter<>(getContext(),android.R.layout.simple_spinner_item,options); a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item); s.setAdapter(a); s.setMinimumHeight(48); return s;
    }
}
