import React from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors } from '../theme';

export function AppShell({ children, refreshing = false }) {
  return (
    <ScrollView
      style={s.root}
      contentContainerStyle={s.content}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      {refreshing && <View style={s.refreshBar}><ActivityIndicator size="small" color={colors.primary}/><Text style={s.refreshText}>Updating…</Text></View>}
      {children}
    </ScrollView>
  );
}

export function Header({ title, subtitle, right, eyebrow }) {
  return <View style={s.header}>
    <View style={{flex:1,minWidth:220}}>
      {eyebrow && <Text style={s.eyebrow}>{eyebrow}</Text>}
      <Text style={s.h1}>{title}</Text>
      {subtitle && <Text style={s.sub}>{subtitle}</Text>}
    </View>
    {right && <View style={{marginTop:4}}>{right}</View>}
  </View>;
}

export function Breadcrumbs({ items = [] }) {
  return <View style={s.breadcrumbs}>{items.map((item,i)=><React.Fragment key={`${item}-${i}`}>
    {i>0 && <Text style={s.crumbSep}>›</Text>}
    <Text style={[s.crumb, i===items.length-1 && s.crumbActive]}>{item}</Text>
  </React.Fragment>)}</View>;
}

export function Card({ children, style }) { return <View style={[s.card, style]}>{children}</View>; }

export function Button({ title, onPress, variant='primary', disabled=false, style }) {
  const bg = variant==='primary' ? colors.primary : variant==='danger' ? colors.danger : variant==='success' ? colors.success : '#fff';
  const fg = variant==='primary' || variant==='danger' || variant==='success' ? '#fff' : colors.primary;
  return <Pressable onPress={onPress} disabled={disabled} style={({pressed})=>[
    s.button,
    {backgroundColor:bg,borderColor:variant==='primary'||variant==='danger'||variant==='success'?bg:'#BFDBFE',opacity: disabled ? 0.45 : (pressed ? 0.78 : 1)},
    style
  ]}><Text style={{color:fg,fontWeight:'800',fontSize:14}}>{title}</Text></Pressable>;
}

export function IconButton({ label, onPress, danger=false }) {
  return <Pressable onPress={onPress} style={({pressed})=>[s.iconButton,{backgroundColor:danger?'#FEF2F2':'#F8FAFC',borderColor:danger?'#FECACA':colors.border,opacity: pressed ? 0.75 : 1}]}>
    <Text style={{fontSize:13,fontWeight:'800',color:danger?colors.danger:colors.text}}>{label}</Text>
  </Pressable>;
}

export function Field({ label, value, onChangeText, placeholder, multiline=false, keyboardType, secureTextEntry }) {
  return <View style={{marginBottom:12}}>{label && <Text style={s.label}>{label}</Text>}<TextInput value={value} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={colors.subtle} multiline={multiline} keyboardType={keyboardType} secureTextEntry={secureTextEntry} style={[s.input,multiline&&{minHeight:105,textAlignVertical:'top'}]}/></View>;
}

export function Select({ label, value, options, onChange }) {
  return <View style={{marginBottom:12}}><Text style={s.label}>{label}</Text><View style={s.wrap}>{options.map(o=><Pressable key={String(o.value)} onPress={()=>onChange(o.value)} style={[s.chip,value===o.value&&s.chipActive]}><Text style={{fontWeight:'700',color:value===o.value?colors.primary:colors.text}}>{o.label}</Text></Pressable>)}</View></View>;
}

export function Badge({ children, tone='blue' }) {
  const map={blue:[colors.blueSoft,colors.primary],green:[colors.greenSoft,colors.success],orange:[colors.orangeSoft,colors.warning],purple:[colors.purpleSoft,colors.purple],pink:[colors.pinkSoft,colors.primary],red:['#FEF2F2',colors.danger]};
  const [bg,fg]=map[tone]||map.blue;
  return <View style={{backgroundColor:bg,paddingHorizontal:9,paddingVertical:5,borderRadius:20,alignSelf:'flex-start'}}><Text style={{color:fg,fontSize:12,fontWeight:'800'}}>{children}</Text></View>;
}

export function Loading({ label='Loading…' }) { return <Card style={s.loading}><ActivityIndicator size="large" color={colors.primary}/><Text style={s.loadingText}>{label}</Text><Text style={s.loadingHint}>Connecting to your learning data</Text></Card>; }

export function ErrorState({ title='Could not load this screen', message='Please check the backend connection and try again.', onRetry }) {
  return <Card style={s.errorCard}><Text style={{fontSize:18,fontWeight:'900',color:colors.navy}}>{title}</Text><Text style={{color:colors.muted,lineHeight:20,marginTop:6}}>{message}</Text>{onRetry&&<View style={{marginTop:14}}><Button title="Try again" onPress={onRetry}/></View>}</Card>;
}


export function SectionTitle({ title, subtitle, right }) {
  return <View style={{flexDirection:'row',alignItems:'flex-end',justifyContent:'space-between',gap:10,marginTop:6,marginBottom:10}}>
    <View style={{flex:1}}>
      <Text style={{fontSize:20,fontWeight:'900',color:colors.navy}}>{title}</Text>
      {subtitle && <Text style={{fontSize:12,color:colors.muted,marginTop:3,lineHeight:18}}>{subtitle}</Text>}
    </View>
    {right}
  </View>;
}

export function ProgressBar({ value=0, height=9, color=colors.primary }) {
  const safe=Math.max(0,Math.min(100,Number(value)||0));
  return <View style={{height,width:'100%',backgroundColor:'#E2E8F0',borderRadius:99,overflow:'hidden'}}>
    <View style={{height,width:`${safe}%`,backgroundColor:color,borderRadius:99}}/>
  </View>;
}

export function Empty({title,message,action}){return <Card style={{alignItems:'center',padding:30}}><Text style={{fontSize:18,fontWeight:'900',color:colors.navy}}>{title}</Text>{message&&<Text style={{color:colors.muted,textAlign:'center',marginTop:6,maxWidth:520}}>{message}</Text>}{action&&<View style={{marginTop:15}}>{action}</View>}</Card>;}

export const s=StyleSheet.create({
 root:{flex:1,backgroundColor:colors.background},
 content:{paddingHorizontal:20,paddingTop:22,paddingBottom:50,width:'100%',maxWidth:1250,alignSelf:'center',minHeight:600},
 header:{flexDirection:'row',alignItems:'center',marginBottom:18,gap:12},
 eyebrow:{fontSize:11,fontWeight:'900',color:colors.primary,textTransform:'uppercase',letterSpacing:1,marginBottom:4},
 h1:{fontSize:28,fontWeight:'900',color:colors.navy},
 sub:{color:colors.muted,marginTop:4,lineHeight:20},
 breadcrumbs:{flexDirection:'row',alignItems:'center',flexWrap:'wrap',gap:5,marginBottom:10},
 crumb:{fontSize:12,color:colors.subtle,fontWeight:'700'},
 crumbActive:{color:colors.text},
 crumbSep:{color:colors.subtle,fontSize:18},
 card:{backgroundColor:'#fff',borderRadius:18,borderWidth:1,borderColor:colors.border,padding:18,marginBottom:14,shadowColor:'#0F172A',shadowOpacity:0.03,shadowRadius:8,shadowOffset:{width:0,height:3}},
 button:{minHeight:42,borderRadius:11,borderWidth:1,paddingHorizontal:15,paddingVertical:10,alignItems:'center',justifyContent:'center'},
 iconButton:{borderWidth:1,borderRadius:10,paddingHorizontal:11,paddingVertical:8},
 input:{borderWidth:1,borderColor:colors.border,borderRadius:11,backgroundColor:'#fff',paddingHorizontal:13,paddingVertical:11,color:colors.text},
 label:{fontSize:12,fontWeight:'800',color:colors.text,marginBottom:6},
 wrap:{flexDirection:'row',flexWrap:'wrap',gap:8},
 chip:{borderWidth:1,borderColor:colors.border,borderRadius:20,paddingHorizontal:12,paddingVertical:8},
 chipActive:{backgroundColor:colors.blueSoft,borderColor:'#93C5FD'},
 loading:{minHeight:190,alignItems:'center',justifyContent:'center'},
 loadingText:{fontWeight:'900',fontSize:16,color:colors.navy,marginTop:12},
 loadingHint:{color:colors.subtle,fontSize:12,marginTop:4},
 errorCard:{backgroundColor:'#FFF7F7',borderColor:'#FECACA'},
 refreshBar:{flexDirection:'row',alignItems:'center',gap:7,marginBottom:10},
 refreshText:{fontSize:12,color:colors.muted,fontWeight:'700'}
});
