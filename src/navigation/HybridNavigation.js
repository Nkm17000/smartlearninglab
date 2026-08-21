import React, {useState} from 'react';
import {Pressable, ScrollView, Text, View, useWindowDimensions} from 'react-native';
import {colors} from '../theme';

const Icon = ({name}) => <Text style={{fontSize:16,width:24,textAlign:'center'}}>{name}</Text>;

export default function HybridNavigation({route,setRoute,logout,admin=false,root=false,children}) {
  const {width} = useWindowDimensions();
  const compact = width < 900;
  const [drawer,setDrawer] = useState(false);

  const top = admin
    ? [['home','⌂','Dashboard'],['courses','▣','Courses'],['quizzes','✓','Test Series'],['ai-lab','✦','AI Lab'],['intelligence','🧠','AI Intelligence'],['students','♙','Students']]
    : [['home','⌂','Home'],['courses','▣','Courses'],['progress','◉','My Learning'],['studio','🧠','AI Studio'],['ai','✦','AI Tutor'],['flashcards','▤','Flashcards']];

  const side = admin
    ? [['questions','Question Bank','Questions and content'],['analytics','Analytics','Platform performance'],...(root?[['staff','Admin & Staff','Manage administrators']]:[])]
    : [['plan','Learning Plan','Personalized roadmap'],['adaptive','Adaptive Tests','Difficulty adjusts to you'],['analytics','Analytics','Performance insights'],['bookmarks','Bookmarks','Saved learning items'],['leaderboard','Leaderboard','Compare your progress'],['certificates','Certificates','Your achievements'],['speaking','Speaking Practice','Build speaking confidence'],['interview','Interview Prep','Practice interviews'],['community','Community','Learn with others'],['notes','Notes','Your personal notes'],['notifications','Notifications','Updates and reminders']];

  const active = route.startsWith('course:') ? 'courses' : route.startsWith('quiz:') ? 'quizzes' : route;
  const go = (r) => { setDrawer(false); setRoute(r); };

  return <View style={{flex:1,backgroundColor:colors.background}}>
    <View style={{backgroundColor:'#fff',borderBottomWidth:1,borderBottomColor:colors.border,zIndex:10}}>
      <View style={{maxWidth:1400,width:'100%',alignSelf:'center',paddingHorizontal:18,paddingVertical:10,flexDirection:'row',alignItems:'center',gap:8}}>
        {compact && <Pressable onPress={()=>setDrawer(true)} style={{width:42,height:42,borderRadius:12,backgroundColor:colors.blueSoft,alignItems:'center',justifyContent:'center',marginRight:4}}><Text style={{fontSize:22,color:colors.navy}}>☰</Text></Pressable>}
        <Pressable onPress={()=>go('home')} style={{width:compact?155:205}}>
          <Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>Smart <Text style={{color:colors.primary}}>Learning Lab</Text></Text>
          {!compact && <Text style={{fontSize:8,color:colors.muted,fontWeight:'900',letterSpacing:1}}>LEARN • PRACTICE • GROW</Text>}
        </Pressable>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{gap:6,alignItems:'center',flexGrow:1}}>
          {top.map(([r,icon,label])=><Pressable key={r} onPress={()=>go(r)} style={{flexDirection:'row',alignItems:'center',gap:5,paddingHorizontal:12,paddingVertical:9,borderRadius:10,backgroundColor:active===r?colors.pinkSoft:'#fff'}}><Icon name={icon}/><Text style={{fontSize:12,fontWeight:'900',color:active===r?colors.primary:colors.text}}>{label}</Text></Pressable>)}
        </ScrollView>
        <View style={{paddingHorizontal:10,paddingVertical:8,borderRadius:10,backgroundColor:'#F8FAFC'}}><Text style={{fontSize:10,fontWeight:'900',color:colors.muted}}>{root?'ROOT ADMIN':admin?'ADMIN':'STUDENT'}</Text></View>
        {!compact && <Pressable onPress={logout} style={{paddingHorizontal:12,paddingVertical:9,borderRadius:10,backgroundColor:'#FFF1F2'}}><Text style={{fontWeight:'900',fontSize:12,color:colors.danger}}>Logout</Text></Pressable>}
      </View>
    </View>

    <View style={{flex:1,flexDirection:'row',maxWidth:1400,width:'100%',alignSelf:'center'}}>
      {!compact && <View style={{width:245,borderRightWidth:1,borderRightColor:colors.border,backgroundColor:'#fff',padding:14}}>
        <Text style={{fontSize:10,fontWeight:'900',color:colors.subtle,letterSpacing:1,marginBottom:10}}>MORE</Text>
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{paddingBottom:30}}>
          {side.map(([r,label,desc])=><Pressable key={r} onPress={()=>go(r)} style={{padding:12,borderRadius:12,marginBottom:5,backgroundColor:active===r?colors.pinkSoft:'#fff'}}>
            <Text style={{fontSize:13,fontWeight:'900',color:active===r?colors.primary:colors.navy}}>{label}</Text>
            <Text style={{fontSize:10,color:colors.muted,marginTop:3}}>{desc}</Text>
          </Pressable>)}
          <Pressable onPress={logout} style={{padding:12,borderRadius:12,marginTop:8,backgroundColor:'#FFF1F2'}}><Text style={{fontSize:13,fontWeight:'900',color:colors.danger}}>Logout</Text></Pressable>
        </ScrollView>
      </View>}
      <View style={{flex:1,minWidth:0}}>{children}</View>
    </View>

    {compact && drawer && <View style={{position:'absolute',top:0,left:0,right:0,bottom:0,zIndex:50,flexDirection:'row'}}>
      <Pressable onPress={()=>setDrawer(false)} style={{flex:1,backgroundColor:'rgba(15,23,42,0.35)'}} />
      <View style={{position:'absolute',left:0,top:0,bottom:0,width:300,backgroundColor:'#fff',padding:18,shadowColor:'#000',shadowOpacity:0.15,shadowRadius:20}}>
        <View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginBottom:18}}><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>Menu</Text><Pressable onPress={()=>setDrawer(false)}><Text style={{fontSize:22,color:colors.muted}}>×</Text></Pressable></View>
        <ScrollView showsVerticalScrollIndicator={false}>
          {side.map(([r,label,desc])=><Pressable key={r} onPress={()=>go(r)} style={{padding:13,borderRadius:12,marginBottom:6,backgroundColor:active===r?colors.pinkSoft:'#fff'}}><Text style={{fontWeight:'900',color:active===r?colors.primary:colors.navy}}>{label}</Text><Text style={{fontSize:10,color:colors.muted,marginTop:3}}>{desc}</Text></Pressable>)}
          <Pressable onPress={logout} style={{padding:13,borderRadius:12,marginTop:8,backgroundColor:'#FFF1F2'}}><Text style={{fontWeight:'900',color:colors.danger}}>Logout</Text></Pressable>
        </ScrollView>
      </View>
    </View>}
  </View>;
}
